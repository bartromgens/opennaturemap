# OpenNatureMap

A web app for browsing nature reserves on an interactive map.

It uses OpenStreetMap data (via Overpass), a Django REST API, and an Angular frontend with vector tiles served by tileserver-gl.

## Setup

### Backend (Django)

1. Create and activate the virtualenv (project root):

   ```bash
   python -m venv env
   source env/bin/activate   # Linux/macOS
   ```

2. Copy the local settings example and edit if needed:

   ```bash
   cp config/settings_local.py.example config/settings_local.py
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations:

   ```bash
   python manage.py migrate
   ```

### Frontend (Angular)

1. Go to the client directory and install dependencies:

   ```bash
   cd client
   npm install
   ```

## Run

### Backend (Django)

From the project root (with virtualenv activated):

```bash
python manage.py runserver
```

API: http://127.0.0.1:8000/

### Tileserver

To serve map tiles, put MBTiles in `data/` and run tileserver-gl:

```bash
docker compose up
```

Tiles: http://localhost:8080/

### Frontend (Angular)

From the `client` directory:

```bash
ng serve
```

App: http://localhost:4200/

## Data

### Import data

Import nature reserves from OpenStreetMap (Overpass API):

```bash
python manage.py import_nature_reserves
```

Useful options:

- `--clear` — clear existing data before importing
- `--province utrecht` or `--province friesland` — limit to one province
- `--bbox min_lon,min_lat,max_lon,max_lat` — custom bounding box
- `--test-region` — small test area (Utrecht)
- `--test-de-deelen` — small test area (Friesland)

### Export to MBTiles

Export the database to GeoJSON and convert to MBTiles for tileserver-gl:

```bash
python manage.py export_to_mbtiles
```

Requires [tippecanoe](https://github.com/felt/tippecanoe) installed.

Options:

- `--output path` — MBTiles output (default: `data/nature_reserves.mbtiles`)
- `--geojson-output path` — intermediate GeoJSON (default: `data/nature_reserves.geojson`)
- `--min-zoom`, `--max-zoom` — zoom range (default 0–14)
- `--layer-name` — layer name in MBTiles (default: `nature_reserves`)
- `--force` — overwrite existing file

## Production

### Deploy

Make sure your changes are pushed to `origin/master`, then run:

```bash
./deploy.sh
```

This SSHes into the VPS, pulls the latest code, rebuilds the Docker images, restarts the containers, and runs migrations.

### Run a management command

To run a Django management command inside the production `api` container:

```bash
docker compose -f docker-compose.prod.yml exec api python manage.py <command>
```

For example, to import nature reserves:

```bash
docker compose -f docker-compose.prod.yml exec api python manage.py import_nature_reserves
```

## Alternatives

- [Protected Planet](https://www.protectedplanet.net) — global database of protected areas (IUCN/UNEP-WCMC)
