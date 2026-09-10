{
  description = "Flake for Vortex";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    treefmt-nix.url = "github:numtide/treefmt-nix";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      treefmt-nix,
      self,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        formatters =
          (treefmt-nix.lib.evalModule pkgs (_: {
            projectRootFile = ".git/config";
            programs = {
              nixfmt.enable = true;
              nixf-diagnose.enable = true;
              toml-sort.enable = true;
              black.enable = true;
            };
          })).config.build;
      in
      {
        devShells.default = pkgs.mkShell {
          meta = {
            license = pkgs.lib.licenses.mit;
          };
          buildInputs = with pkgs; [
            python311
            postgresql_14
            just
            nodejs
          ];

          shellHook =
            if !pkgs.stdenv.isDarwin then
              ''
                #!/bin/bash
                COMMAND=$(awk -F: -v user=$USER 'user == $1 {print $NF}' /etc/passwd)
                if [ "$COMMAND" != *bash* ]; then
                  $COMMAND
                  exit
                fi
              ''
            else
              ''
                #!/bin/bash
                COMMAND=$(dscl . -read $HOME 'UserShell' | grep --only-matching '/.*')
                if [ "$COMMAND" != *bash* ]; then
                  $COMMAND
                  exit
                fi
              '';
        };

        packages.default = pkgs.python311Packages.buildPythonPackage {
          name = "vortex";
          src = ./.;
          pyproject = true;
          nativeBuildInputs = [ pkgs.python311Packages.poetry-core ];
        };

        formatter = formatters.wrapper;
        checks.formatting = formatters.check self;
      }
    );
}
