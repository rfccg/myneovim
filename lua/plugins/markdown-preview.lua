if vim.fn.has("linux") ~= 1 or not vim.env.SSH_CONNECTION or vim.env.DISPLAY or vim.env.WAYLAND_DISPLAY then
  return {}
end

return {
  {
    "iamcco/markdown-preview.nvim",
    optional = true,
    -- Use the version in the plugin's yarn.lock; newer versions omit msgpack-lite.
    build = "cd app && npm install --ignore-scripts --no-save --package-lock=false @chemzqm/neovim@5.7.9",
    init = function()
      vim.g.mkdp_open_to_the_world = 0
      vim.g.mkdp_open_ip = "127.0.0.1"
      vim.g.mkdp_port = 18765
      vim.g.mkdp_browserfunc = "mkdp#util#echo_url"
    end,
  },
}
