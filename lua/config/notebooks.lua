local M = {}
local root = vim.fn.resolve(vim.fn.stdpath("config"))
M.provider = vim.fn.stdpath("data") .. "/notebook-provider/bin/python"
local busy = {}
local pending_import = {}

local function text(buf)
  return table.concat(vim.api.nvim_buf_get_lines(buf, 0, -1, false), "\n") .. "\n"
end

local function request(mode, buf, path)
  local kernelspec
  if mode == "write" then
    local ok, active = pcall(vim.fn.MoltenRunningKernels, true)
    if ok and #active == 1 then
      kernelspec = vim.fn.MoltenKernelSpec(active[1])
    end
  end
  local result = vim
    .system({ M.provider, root .. "/scripts/notebook.py" }, {
      text = true,
      stdin = vim.json.encode({
        mode = mode,
        path = path or vim.api.nvim_buf_get_name(buf),
        text = text(buf),
        kernelspec = kernelspec,
      }),
    })
    :wait()
  if result.code ~= 0 then
    error(vim.trim(result.stderr), 0)
  end
  return vim.json.decode(result.stdout)
end

local function guarded(callback)
  return function(...)
    local ok, err = pcall(callback, ...)
    if not ok then
      vim.notify("Notebook: " .. tostring(err), vim.log.levels.ERROR)
    end
  end
end

local function companion_guard(buf, info)
  for _, path in ipairs(info.paths or {}) do
    for _, other in ipairs(vim.api.nvim_list_bufs()) do
      if other ~= buf and vim.api.nvim_buf_is_loaded(other) then
        local name = vim.api.nvim_buf_get_name(other)
        if vim.fn.resolve(name) == vim.fn.resolve(path) and vim.bo[other].modified then
          error("Save aborted: unsaved companion buffer " .. path, 0)
        end
      end
    end
  end
end

local function kernels()
  if vim.fn.exists(":MoltenInit") ~= 2 then
    return {}
  end
  return vim.fn.MoltenRunningKernels(true)
end

local function export(buf, target)
  local active = kernels()
  if #active == 0 then
    return
  end
  if #active ~= 1 then
    error("Content saved; output export requires exactly one kernel attached to this buffer", 0)
  end
  request("check", buf, target)
  -- Molten splits command arguments on whitespace. Stage under tempname instead of
  -- passing the notebook's (possibly spaced) filename. Never let it write the original.
  local stage = vim.fn.tempname() .. ".ipynb"
  vim.fn.writefile(vim.fn.readfile(target, "b"), stage, "b")
  local before = vim.uv.fs_stat(stage).mtime
  local ok, err = pcall(vim.cmd, "MoltenExportOutput! " .. stage .. " " .. active[1])
  local after = vim.uv.fs_stat(stage).mtime
  -- Molten reports matching failures through scheduled notifications, not thrown
  -- exceptions. Its exporter writes only on success; unchanged mtime means bail.
  if ok and before.sec == after.sec and before.nsec == after.nsec then
    ok, err =
      false,
      "Molten wrote no results (running/queued cells, no outputs, or mismatched cell ranges). Wait or rerun complete cells, then save again."
  end
  if ok then
    -- Same-directory replacement preserves the old notebook if export fails.
    local fd, replacement = vim.uv.fs_mkstemp(target .. ".nvim-output-XXXXXX")
    if not fd then
      vim.fn.delete(stage)
      error("Content saved; cannot stage output replacement: " .. tostring(replacement), 0)
    end
    vim.uv.fs_close(fd)
    ok, err = pcall(function()
      assert(vim.uv.fs_copyfile(stage, replacement))
      assert(vim.uv.fs_chmod(replacement, vim.uv.fs_stat(target).mode % 512))
      assert(vim.uv.fs_rename(replacement, target))
    end)
    vim.fn.delete(replacement)
  end
  vim.fn.delete(stage)
  if not ok then
    error("Content saved, but output export failed: " .. tostring(err), 0)
  end
end

function M.save(buf)
  buf = buf or vim.api.nvim_get_current_buf()
  if busy[buf] then
    error("Notebook save already in progress", 0)
  end
  busy[buf] = true
  local ok, err = pcall(function()
    local info = request("info", buf)
    if info.target == vim.NIL or not info.target then
      return
    end
    companion_guard(buf, info)
    info = request("write", buf)
    -- Conversion is complete before Molten sees the notebook.
    export(buf, info.target)
    for _, path in ipairs(info.paths or {}) do
      for _, other in ipairs(vim.api.nvim_list_bufs()) do
        if other ~= buf and vim.api.nvim_buf_is_loaded(other) and vim.api.nvim_buf_get_name(other) == path then
          vim.api.nvim_buf_call(other, function()
            vim.cmd("checktime")
          end)
        end
      end
    end
  end)
  busy[buf] = nil
  if not ok then
    error(err, 0)
  end
end

function M.pair()
  local buf = vim.api.nvim_get_current_buf()
  if vim.bo.filetype ~= "python" or not vim.api.nvim_buf_get_name(buf):match("%.py$") then
    error("NotebookPair requires a named Python .py buffer", 0)
  end
  if vim.bo.modified then
    error("Save the Python buffer before pairing", 0)
  end
  local info = request("info", buf)
  companion_guard(buf, info)
  request("pair", buf)
  vim.cmd("edit")
  vim.cmd("write")
end

function M.import(buf, ready_kernel)
  if not vim.api.nvim_buf_is_valid(buf) or vim.b[buf].notebook_imported or vim.b[buf].notebook_importing then
    return
  end
  vim.api.nvim_buf_call(buf, function()
    local active = kernels()
    local info = request("info", buf)
    if
      #active ~= 1
      or (ready_kernel and active[1] ~= ready_kernel)
      or info.target == vim.NIL
      or not info.target
      or vim.fn.filereadable(info.target) ~= 1
    then
      return
    end
    local stage = vim.fn.tempname() .. ".ipynb"
    vim.fn.writefile(vim.fn.readfile(info.target, "b"), stage, "b")
    -- Reentrancy guard is separate from completion, so a failed import can retry.
    vim.b[buf].notebook_importing = true
    local ok, err = pcall(vim.cmd, "MoltenImportOutput " .. stage .. " " .. active[1])
    vim.fn.delete(stage)
    vim.b[buf].notebook_importing = nil
    if not ok then
      error(err, 0)
    end
    vim.b[buf].notebook_imported = true
  end)
end

function M.setup_navigator()
  -- The installed adapter appends a marker at EOF and adds one to the range.
  -- Adapt only its Molten bridge; retain Navigator's cell selection/navigation.
  local get_repl = require("notebook-navigator.repls")
  package.loaded["notebook-navigator.repls"] = function(provider)
    if provider ~= "molten" then
      return get_repl(provider)
    end
    return function(first, last)
      local active = kernels()
      if #active ~= 1 then
        error("Select exactly one buffer kernel before execution", 0)
      end
      local lines = vim.api.nvim_buf_get_lines(0, first - 1, last, false)
      local executable = vim.tbl_filter(function(line)
        return line:match("%S") and not line:match("^%s*#")
      end, lines)
      if #executable > 0 then
        M.import(vim.api.nvim_get_current_buf())
        vim.b.notebook_imported = true
        vim.fn.MoltenEvaluateRange(active[1], first, last)
      end
      return true
    end
  end
  require("notebook-navigator").setup({ repl_provider = "molten", syntax_highlight = true })
end

local function run(move)
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local row = vim.api.nvim_win_get_cursor(0)[1]
  local marker
  for i = row, 1, -1 do
    if lines[i]:match("^# %%%%") then
      marker = lines[i]
      break
    end
  end
  if marker and (marker:match("%[markdown%]") or marker:match("%[raw%]")) then
    if move then
      require("notebook-navigator").move_cell("d")
    end
    return
  end
  if #kernels() ~= 1 then
    vim.notify("Select one kernel with <localleader>ni before running cells", vim.log.levels.WARN)
    return
  end
  local nn = require("notebook-navigator")
  if move then
    nn.run_and_move()
  else
    nn.run_cell()
  end
end

function M.visual()
  M.import(vim.api.nvim_get_current_buf())
  vim.b.notebook_imported = true
  vim.cmd("MoltenEvaluateVisual")
end

function M.run_all()
  local cursor = vim.api.nvim_win_get_cursor(0)
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local starts = { 1 }
  for row, line in ipairs(lines) do
    if row > 1 and line:match("^# %%%%") then
      table.insert(starts, row)
    end
  end
  local ok, err = pcall(function()
    for _, row in ipairs(starts) do
      vim.api.nvim_win_set_cursor(0, { row, 0 })
      run(false)
    end
  end)
  vim.api.nvim_win_set_cursor(0, cursor)
  if not ok then
    error(err, 0)
  end
end

function M.attach(buf)
  if vim.b[buf].notebook_mappings then
    return
  end
  vim.b[buf].notebook_mappings = true
  local function map(mode, lhs, rhs, desc)
    -- Do not shadow existing mappings from the user's configuration.
    if vim.fn.maparg(lhs, mode) == "" then
      vim.keymap.set(mode, lhs, rhs, { buffer = buf, silent = true, desc = "Notebook: " .. desc })
    end
  end
  map("n", "<localleader>ni", "<cmd>MoltenInit<cr>", "select kernel")
  map("n", "<localleader>nr", function()
    run(false)
  end, "run cell")
  map("n", "<localleader>nn", function()
    run(true)
  end, "run cell and advance")
  map("n", "<localleader>nA", M.run_all, "run all code cells")
  map("x", "<localleader>nr", ":<C-u>lua require('config.notebooks').visual()<cr>", "run selection")
  map("n", "<localleader>np", function()
    require("notebook-navigator").move_cell("u")
  end, "previous cell")
  map("n", "<localleader>nj", function()
    require("notebook-navigator").move_cell("d")
  end, "next cell")
  map("n", "<localleader>nx", "<cmd>MoltenInterrupt<cr>", "interrupt")
  map("n", "<localleader>nR", "<cmd>MoltenRestart<cr>", "restart kernel")
  map("n", "<localleader>no", "<cmd>noautocmd MoltenEnterOutput<cr>", "enter full output")
  map("n", "<localleader>nh", "<cmd>MoltenOpenInBrowser<cr>", "HTML in browser")
  map("n", "<localleader>nv", "<cmd>MoltenImagePopup<cr>", "external image viewer")
  map("n", "<localleader>ns", "<cmd>NotebookSync<cr>", "save and synchronize")
  map("n", "<localleader>nP", "<cmd>NotebookPair<cr>", "pair Python script")
  map("n", "<localleader>na", function()
    require("notebook-navigator").add_cell_below()
  end, "add cell below")
  map("n", "<localleader>nb", function()
    require("notebook-navigator").split_cell()
  end, "split cell")
end

function M.setup()
  local group = vim.api.nvim_create_augroup("NotebookWorkflow", { clear = true })
  vim.api.nvim_create_autocmd("FileType", {
    group = group,
    pattern = "python",
    callback = function(ev)
      M.attach(ev.buf)
    end,
  })
  vim.api.nvim_create_autocmd("BufWritePost", {
    group = group,
    pattern = "*.py",
    callback = guarded(function(ev)
      M.save(ev.buf)
    end),
  })
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "MoltenInitPost",
    callback = function()
      pending_import[vim.api.nvim_get_current_buf()] = true
    end,
  })
  vim.api.nvim_create_autocmd("User", {
    group = group,
    pattern = "MoltenKernelReady",
    callback = function(ev)
      local kernel = ev.data and ev.data.kernel_id
      vim.schedule(guarded(function()
        for buf in pairs(pending_import) do
          if vim.api.nvim_buf_is_valid(buf) then
            M.import(buf, kernel)
          end
          if not vim.api.nvim_buf_is_valid(buf) or vim.b[buf].notebook_imported then
            pending_import[buf] = nil
          end
        end
      end))
    end,
  })
  vim.api.nvim_create_user_command("NotebookPair", guarded(M.pair), { force = true })
  vim.api.nvim_create_user_command(
    "NotebookSync",
    guarded(function()
      local path = vim.api.nvim_buf_get_name(0)
      local info = request("info", vim.api.nvim_get_current_buf())
      if info.target == vim.NIL or not info.target then
        error("Not paired; use :NotebookPair first", 0)
      end
      vim.cmd("write")
      if path:match("%.py$") then
        -- BufWritePost already completed synchronization and export.
        return
      end
    end),
    { force = true }
  )
end

function M.setup_jupytext()
  -- Upstream uses a same-stem .py file as a conversion scratch file. Isolate it
  -- so opening ipynb never reads, overwrites, or deletes the user's paired script.
  local scratch = {}
  require("jupytext.utils").get_ipynb_metadata = function(filename)
    local notebook = vim.json.decode(table.concat(vim.fn.readfile(filename), "\n"))
    local metadata = notebook.metadata or {}
    local language = (metadata.kernelspec or {}).language or (metadata.language_info or {}).name or "python"
    if language ~= "python" then
      error("This notebook setup supports Python only (found " .. language .. ")", 0)
    end
    return { language = "python", extension = "py" }
  end
  require("jupytext.utils").get_jupytext_file = function(filename)
    if not scratch[filename] then
      scratch[filename] = vim.fn.tempname() .. ".py"
    end
    return scratch[filename]
  end
  require("jupytext").setup({ style = "percent", output_extension = "py", force_ft = "python" })
  local handlers = vim.api.nvim_get_autocmds({ group = "jupytext-nvim", event = "BufReadCmd" })
  assert(#handlers == 1, "jupytext.nvim read handler changed; review notebook adaptation")
  local read = handlers[1].callback
  vim.api.nvim_del_autocmd(handlers[1].id)
  vim.api.nvim_create_autocmd("BufReadCmd", {
    group = "jupytext-nvim",
    pattern = "*.ipynb",
    callback = function(ev)
      -- BufReadCmd suppresses the normal read events. This installed LazyVim
      -- loads LSP on BufReadPre, not User LazyFile (the upstream workaround).
      vim.api.nvim_exec_autocmds("BufReadPre", { buffer = ev.buf, modeline = false })
      -- Propagate conversion errors instead of leaving a half-converted buffer.
      read(ev)
      vim.api.nvim_clear_autocmds({
        group = "jupytext-nvim",
        event = { "BufWriteCmd", "FileWriteCmd" },
        buffer = ev.buf,
      })
      vim.api.nvim_create_autocmd({ "BufWriteCmd", "FileWriteCmd" }, {
        group = "jupytext-nvim",
        buffer = ev.buf,
        callback = function(write)
          if write.event == "FileWriteCmd" then
            error("Notebook :write to another filename is disabled; save then copy the ipynb explicitly", 0)
          end
          M.save(ev.buf)
          vim.bo[ev.buf].modified = false
          vim.api.nvim_exec_autocmds("BufWritePost", { buffer = ev.buf })
        end,
      })
      M.attach(ev.buf)
      vim.api.nvim_exec_autocmds("BufReadPost", { buffer = ev.buf, modeline = false })
    end,
  })
  require("jupytext.commands").run_jupytext_command = function(input, options)
    local executable = M.provider:gsub("/python$", "/jupytext")
    local command = vim.fn.shellescape(executable) .. " " .. input
    for option, value in pairs(options) do
      command = command .. " " .. option .. (value == "" and "" or "=" .. value)
    end
    local result = vim.fn.system(command)
    if vim.v.shell_error ~= 0 then
      error("Jupytext conversion failed: " .. result, 0)
    end
  end
end

return M
