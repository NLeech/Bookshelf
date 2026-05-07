# Installation

- Install docker and docker-compose (https://docs.docker.com/engine/install/debian/#install-using-the-repository)

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

#  install the latest version
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
- Ensure docker is running and add your user to the docker group
```bash
sudo systemctl status docker
```
If docker is not running, start it with:
```bash
sudo systemctl start docker
```

- Add user to the docker group (allows using docker command without sudo)
``` bash
sudo usermod -aG docker $USER
```

## Changing Docker's storage location (optional)
- Stop daemon
``` bash
sudo systemctl stop docker docker.socket containerd
```
- Move Existing Data: Use rsync to preserve permissions and ownership.
```bash
# Create the new directory
sudo mkdir -p /new/path/docker
# Copy existing files
sudo rsync -aqxP /var/lib/docker/ /new/path/docker
```
- Update Configuration: Edit (or create) the configuration file at /etc/docker/daemon.json.
```json
{
  "data-root": "/new/path/docker"
}
```
- Restart Docker:
```bash
sudo systemctl daemon-reload
sudo systemctl start docker
```

## Setup CD process with GitHub
- Generate a GitHub Personal Access Token (PAT)
To push and pull images from the GitHub Container Registry (GHCR), you need authentication.

1. In GitHub, go to your user Settings -> Developer settings -> Personal access tokens -> Tokens (classic).
2. Generate a new token. Give it the write:packages and read:packages scopes.
3. Copy the token.
4. Go to the Bookshelf repository Settings -> Secrets and variables -> Actions.
5. Create a new repository secret named CR_PAT and paste the token.

- Authenticate Docker with GitHub so it can pull the private image
``` bash
echo "YOUR_COPIED_PAT_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## Setting up
- Clone the project repository and navigate to the project directory
```bash
git clone https://github.com/NLeech/Bookshelf.git
cd Bookshelf
```

- Create images
``` bash
docker compose pull web
docker compose build
```
- Run containers
``` bash
docker compose up -d
```

- Add languages using Django admin.

- Load Flibusta dump
``` bash
docker compose run --rm web python /Bookshelf/bookshelf/manage.py import_flibusta_dump
```

- Import books
``` bash
docker compose run --rm -v "/mnt/stor/Library:/import:ro" web python /Bookshelf/bookshelf/manage.py import_flibusta_books --formats fb2 epub --genres Фантастика --langs en --path /import 
```



# Test installation
- Install uv package manager (https://docs.astral.sh/uv/getting-started/installation/)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Install psycopg2 build dependencies
```bash
sudo apt install libpq-dev
```
- Clone the project repository and navigate to the project directory
```bash
mkdir testdir
cd testdir
git clone -b dev https://github.com/NLeech/Bookshelf.git
cd Bookshelf
```
- Create virtual environment and install dependencies
```bash
uv venv
source .venv/bin/activate
uv sync
```
- Create a .env_ file with the necessary environment variables
- run PostgreSQL and Redis servers
```bash
sudo docker compose -f db-compose.yml up -d
```
- Apply database migrations
```bash
uv run bookshelf\manage.py migrate
```
- Create a superuser for the admin interface
```bash
uv run bookshelf\manage.py createsuperuser
```
- Run a development server
```bash
uv run bookshelf\python manage.py runserver
```


{
    "formats": ["fb2", "epub"],
    "genres": ["Фантастика"],
    "langs": ["uk", "en"]
}
