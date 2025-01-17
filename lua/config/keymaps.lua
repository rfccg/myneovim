-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here
local keymap = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }

keymap("n", "m.", "//{<cr>", opts)
keymap("n", "m,", "?{<cr>", opts)
keymap("v", "p", '"_dP', opts)
--keymap("v", "m", ":m .+1<CR>==", {})
--keymap("v", "M", ":m .-2<CR>==", {})
