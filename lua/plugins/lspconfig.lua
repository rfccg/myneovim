return {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        zls = {},
        jdtls = {},
        gopls = {
            settings = {
              gopls = {
                gofumpt = true,
                codelenses = {
                  gc_details = false,
                  generate = true,
                  regenerate_cgo = true,
                  run_govulncheck = true,
                  test = true,
                  tidy = true,
                  upgrade_dependency = true,
                  vendor = true,
                },
                hints = {
                  assignVariableTypes = true,
                  compositeLiteralFields = true,
                  compositeLiteralTypes = true,
                  constantValues = true,
                  functionTypeParameters = true,
                  parameterNames = true,
                  rangeVariableTypes = true,
                },
                analyses = {
                  fieldalignment = true,
                  nilness = true,
                  unusedparams = true,
                  unusedwrite = true,
                  useany = true,
                },
                usePlaceholders = true,
                completeUnimported = true,
                staticcheck = true,
                directoryFilters = { "-.git", "-.vscode", "-.idea", "-.vscode-test", "-node_modules" },
                semanticTokens = true,
              },
            },
        },
        metals = {
            keys = {
              {
                "<leader>me",
                function()
                  require("telescope").extensions.metals.commands()
                end,
                desc = "Metals commands",
              },
              {
                "<leader>mc",
                function()
                  require("metals").compile_cascade()
                end,
                desc = "Metals compile cascade",
              },
              {
                "<leader>mh",
                function()
                  require("metals").hover_worksheet()
                end,
                desc = "Metals hover worksheet",
              },
            },
            init_options = {
              statusBarProvider = "off",
            },
            settings = {
              showImplicitArguments = true,
              excludedPackages = { "akka.actor.typed.javadsl", "com.github.swagger.akka.javadsl" },
            },
        },
      },
      setup = {
        metals = function(_, opts)
          local metals = require("metals")
          local metals_config = vim.tbl_deep_extend("force", metals.bare_config(), opts)
          metals_config.on_attach = LazyVim.has("nvim-dap") and metals.setup_dap or nil
  
          local nvim_metals_group = vim.api.nvim_create_augroup("nvim-metals", { clear = true })
          vim.api.nvim_create_autocmd("FileType", {
            pattern = { "scala", "sbt" },
            callback = function()
              metals.initialize_or_attach(metals_config)
            end,
            group = nvim_metals_group,
          })
          return true
        end,
      },
    },
  }