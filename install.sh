#!/bin/sh
# Install Karyo on macOS or Linux without cloning the repository.
set -eu
case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo 'Use macOS, Linux, or Windows with WSL.' >&2; exit 1 ;;
esac
if ! command -v uv >/dev/null 2>&1; then
  echo 'Installing uv…'
  installer=$(mktemp)
  trap 'rm -f "$installer"' EXIT HUP INT TERM
  curl -fsSL https://astral.sh/uv/install.sh -o "$installer"
  sh "$installer"
  export PATH="$HOME/.local/bin:$PATH"
fi
uv tool install --no-cache --refresh --reinstall --python 3.13 --from 'https://github.com/chandan-123kumar/karyo/archive/refs/heads/main.zip' karyo
uv tool update-shell
bin_dir=$(uv tool dir --bin)
echo 'Karyo installed. Connecting your Hugging Face account…'
"$bin_dir/karyo" login
echo 'Open a new terminal, enter your project folder, and run: karyo'
