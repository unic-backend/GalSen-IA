#!/usr/bin/env bash
# Installs the external coding engines in ISOLATED environments (ADR-028).
#
# Why isolation is not a preference here: installing `aider-chat` into the main
# GalSen IA environment was tried, and it downgraded numpy to 1.26 to satisfy
# its own dependency tree. That broke `opencv-python-headless`, and with it the
# Vision Intelligence Engine — `import cv2` failed platform-wide. The finding is
# recorded in ADR-028; this script is the consequence.
#
# Each engine gets its own virtualenv. GalSen IA only ever calls the resulting
# executable, so their dependency trees never meet the platform's.
#
# Usage:
#   scripts/install_coding_engines.sh              # every engine
#   scripts/install_coding_engines.sh aider        # one engine
#
# After installing, export the paths it prints (add them to your shell profile
# or to the service unit that runs GalSen IA).

set -euo pipefail

RACINE="${GALSEN_ENGINES_ROOT:-/opt/galsen-engines}"
MOTEURS=("${@:-aider swe_agent}")
# shellcheck disable=SC2206 # word splitting is what we want for the default
MOTEURS=(${MOTEURS[*]})

installer() {
    local nom="$1" paquet="$2" binaire="$3" variable="$4"
    local venv="$RACINE/$nom"

    echo "==> $nom : $venv"
    python3 -m venv "$venv"
    "$venv/bin/pip" install --quiet --upgrade pip
    "$venv/bin/pip" install --quiet "$paquet"

    if [ ! -x "$venv/bin/$binaire" ]; then
        echo "    ÉCHEC : $venv/bin/$binaire absent après installation." >&2
        return 1
    fi
    echo "    $("$venv/bin/$binaire" --version 2>&1 | head -1)"
    echo "    export $variable=$venv/bin/$binaire"
}

for moteur in "${MOTEURS[@]}"; do
    case "$moteur" in
        aider)
            installer aider aider-chat aider GALSEN_AIDER_BIN
            ;;
        swe_agent|sweagent)
            # SWE-agent also needs Docker at run time: it executes the agent in
            # a container. The adapter reports that separately when it is absent.
            installer swe_agent sweagent sweagent GALSEN_SWE_AGENT_BIN
            ;;
        openhands)
            echo "==> openhands : no local install."
            echo "    OpenHands runs as a container; GalSen IA talks to it over HTTP."
            echo "    docker run -d -p 8010:8000 ghcr.io/openhands/agent-server:latest-python"
            echo "    export GALSEN_OPENHANDS_URL=http://localhost:8010"
            ;;
        *)
            echo "Moteur inconnu : $moteur (attendu : aider, swe_agent, openhands)" >&2
            exit 2
            ;;
    esac
done

echo
echo "Vérification : python -c \"from src.integration.engine_registry import get_shared_registry as r; print(r().get('coding').status())\""
