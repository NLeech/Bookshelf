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

## Test installation
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
- run PostgreSQL server
```bash
sudo docker compose -f postgres-compose.yml up -d
```
- Apply database migrations
```bash
cd bookshelf
python manage.py migrate
```
- Create a superuser for the admin interface
```bash
python manage.py createsuperuser
```
- Run a development server
```bash
python manage.py runserver
```



