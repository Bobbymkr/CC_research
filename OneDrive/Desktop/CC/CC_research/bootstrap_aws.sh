#!/bin/bash
# ==============================================================================
# RAASA AWS EC2 Bootstrapper (Ubuntu 22.04 LTS / 24.04 LTS)
# ==============================================================================
# This script prepares a completely fresh AWS EC2 instance to run RAASA autonomously.
# It installs Docker, Python 3, project dependencies, and triggers the core experiment.
#
# Usage:
#   chmod +x bootstrap_aws.sh
#   ./bootstrap_aws.sh
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status

# 1. Update the system
echo "[RAASA] Updating APT packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. Install Python3 and PIP
echo "[RAASA] Installing Python3 and Pip..."
sudo apt-get install -y python3 python3-pip python3-venv

# 3. Install Docker (The official way)
if ! command -v docker &> /dev/null
then
    echo "[RAASA] Docker not found. Installing Docker Engine..."
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
else
    echo "[RAASA] Docker is already installed."
fi

# Ensure the current user can run Docker commands without sudo
echo "[RAASA] Configuring Docker permissions..."
sudo groupadd docker || true
sudo usermod -aG docker $USER
sudo chmod 666 /var/run/docker.sock || true

# 4. Set up Python Virtual Environment & Install RAASA dependencies
echo "[RAASA] Setting up Python dependencies..."
python3 -m venv venv
source venv/bin/activate

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "[RAASA Warning] requirements.txt not found. Installing defaults..."
    pip install psutil setuptools pyyaml pytest numpy scikit-learn seaborn matplotlib
fi

# 5. Make all python scripts in scratch executable if needed
chmod +x scratch/run_all_py.py || true

echo "=============================================================================="
echo " AWS BOOTSTRAP COMPLETE "
echo "=============================================================================="
echo "The instance is configured. To run RAASA's evaluation benchmarks natively:"
echo ""
echo "  source venv/bin/activate       # Activate the environment"
echo "  export PYTHONPATH=."
echo "  python raasa/experiments/run_experiment.py --mode raasa --scenario small_tuned --duration 60"
echo "=============================================================================="
