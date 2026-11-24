local terminal = vim.env.TERM_PROGRAM or ""
local images = (terminal == "kitty" or terminal == "WezTerm" or terminal == "ghostty")
  and vim.fn.executable("magick") == 1
  and not vim.env.TMUX -- tmux needs explicit passthrough configuration first

return {
  {
    "benlubas/molten-nvim",
    lazy = false,
    build = function(plugin)
      local result = vim
        .system({
          require("config.notebooks").provider,
          vim.fn.stdpath("config") .. "/scripts/patch_molten.py",
          plugin.dir,
        }, { text = true })
        :wait()
      assert(result.code == 0, result.stderr)
      vim.cmd("UpdateRemotePlugins")
    end,
    init = function()
      vim.g.molten_auto_init_behavior = "raise"
      vim.g.molten_auto_open_output = false
      vim.g.molten_auto_open_html_in_browser = false
      vim.g.molten_virt_text_output = true
      vim.g.molten_virt_lines_off_by_1 = false
      vim.g.molten_virt_text_max_lines = 12
      vim.g.molten_output_win_max_height = 30
      vim.g.molten_output_win_max_width = 120
      vim.g.molten_wrap_output = true
      vim.g.molten_image_provider = images and "image.nvim" or "none"
    end,
  },
  {
    "3rd/image.nvim",
    enabled = images,
    lazy = false,
    opts = {
      backend = "kitty",
      processor = "magick_cli",
      integrations = { markdown = { enabled = false } },
      max_height_window_percentage = 40,
      window_overlap_clear_enabled = true,
    },
  },
  {
    "GCBallesteros/NotebookNavigator.nvim",
    lazy = false,
    dependencies = { "benlubas/molten-nvim" },
    config = function()
      require("config.notebooks").setup_navigator()
      require("config.notebooks").setup()
    end,
  },
  {
    "GCBallesteros/jupytext.nvim",
    lazy = false,
    dependencies = { "GCBallesteros/NotebookNavigator.nvim" },
    config = function()
      require("config.notebooks").setup_jupytext()
    end,
  },
}
