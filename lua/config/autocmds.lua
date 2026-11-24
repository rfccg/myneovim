-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
--
-- Add any additional autocmds here
-- with `vim.api.nvim_create_autocmd`
--
-- Or remove existing autocmds by their group name (which is prefixed with `lazyvim_` for the defaults)
-- e.g. vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell")

-- Copy remote yanks without making paste query the desktop clipboard.
if vim.env.SSH_CONNECTION and vim.env.TERM_PROGRAM == "herdr" then
  local copy = require("vim.ui.clipboard.osc52").copy("+")

  vim.api.nvim_create_autocmd("TextYankPost", {
    group = vim.api.nvim_create_augroup("HerdrClipboardYank", { clear = true }),
    callback = function()
      local event = vim.v.event
      if event.operator ~= "y" or event.regname ~= "" then
        return
      end

      local lines = event.regcontents
      if event.regtype == "V" then
        lines[#lines + 1] = ""
      end
      copy(lines)
    end,
  })
end
