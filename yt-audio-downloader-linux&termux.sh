#!/usr/bin/env bash

# Colores y Estética
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

trap "echo -e '\n${RED}Interrumpido.${NC}'; exit" INT

# ================= 1. Auto-Instalación y Entorno =================
clear
echo -e "${CYAN}Verificando entorno...${NC}"

if [ -n "$PREFIX" ] && [[ "$PREFIX" == *"com.termux"* ]]; then
    PLATFORM="termux"
    if [ ! -d "$HOME/storage" ]; then
        echo -e "${YELLOW}Configurando almacenamiento...${NC}"
        termux-setup-storage
        sleep 2
    fi
    # Añadimos termux-api para el selector de archivos
    for pkg in yt-dlp ffmpeg coreutils termux-api; do
        if ! command -v "$pkg" >/dev/null 2>&1; then
            echo -e "${BLUE}Instalando $pkg...${NC}"
            pkg install -y "$pkg"
        fi
    done
else
    PLATFORM="linux"
    for pkg in yt-dlp ffmpeg; do
        if ! command -v "$pkg" >/dev/null 2>&1; then
            echo -e "${RED}Error: Instala $pkg (ej: sudo apt install $pkg)${NC}"
            exit 1
        fi
    done
fi

# ================= 2. Selector de Carpeta (Picker) =================
echo -e "\n${YELLOW}--- Configuración de Directorio ---${NC}"
echo "1) Usar carpeta por defecto"
echo "2) Abrir selector VISUAL (Picker)"
echo "3) Escribir ruta manualmente"
read -rp "Selección: " DIR_MODE

DEST=""
case "$DIR_MODE" in
    1) 
        [ "$PLATFORM" = "termux" ] && DEST="$HOME/storage/downloads/Music" || DEST="$HOME/Music"
        ;;
    2)
        if [ "$PLATFORM" = "termux" ]; then
            echo -e "${BLUE}Abriendo selector de Android...${NC}"
            # Nota: termux-storage-get permite elegir un destino
            DEST=$(termux-storage-get "$HOME/storage/downloads/folder_picker_tmp" 2>/dev/null)
            # Limpiamos el path si devuelve un archivo en lugar de carpeta
            DEST=$(dirname "$DEST")
        else
            if command -v zenity >/dev/null 2>&1; then
                DEST=$(zenity --file-selection --directory --title="Selecciona carpeta de destino")
            elif command -v kdialog >/dev/null 2>&1; then
                DEST=$(kdialog --getexistingdirectory)
            else
                echo -e "${RED}No se encontró Zenity o KDialog. Instala 'zenity' en Linux.${NC}"
            fi
        fi
        ;;
    3)
        read -rp "Ingresa la ruta completa: " DEST
        ;;
esac

# Validación final de ruta
[ -z "$DEST" ] && echo -e "${RED}Ruta no válida. Usando carpeta actual.${NC}" && DEST="."
mkdir -p "$DEST" && cd "$DEST" || exit 1
echo -e "${GREEN}Destino:${NC} $(pwd)"

# ================= 3. Análisis de Playlist =================
echo -e "\n"
read -rp "Pega la URL de la Playlist: " URL
[ -z "$URL" ] && exit 1

echo -e "${BLUE}Analizando...${NC}"
METADATA=$(yt-dlp --flat-playlist --print "%(playlist_title)s|%(playlist_uploader)s" --playlist-items 1 "$URL" 2>/dev/null)
[ -z "$METADATA" ] && echo -e "${RED}Error: Playlist no accesible.${NC}" && exit 1

PLAYLIST_TITLE=$(echo "$METADATA" | cut -d'|' -f1)
PLAYLIST_DIR="$DEST/$PLAYLIST_TITLE"
ARCHIVE="$PLAYLIST_DIR/.ytdlp-archive.txt"
mkdir -p "$PLAYLIST_DIR"

# Obtención de IDs y conteo
ALL_IDS=$(yt-dlp --flat-playlist --get-id "$URL" 2>/dev/null)
TOTAL=$(echo "$ALL_IDS" | wc -l)
[ -f "$ARCHIVE" ] && EXISTING=$(grep -Fxf "$ARCHIVE" <(echo "$ALL_IDS") | wc -l) || EXISTING=0
NEW=$((TOTAL - EXISTING))

echo -e "Playlist: ${GREEN}$PLAYLIST_TITLE${NC} | Nuevos: ${YELLOW}$NEW${NC}"
[ "$NEW" -le 0 ] && echo -e "${GREEN}Todo actualizado.${NC}" && exit 0

# ================= 4. Modo de Operación =================
echo -e "\n${CYAN}Selecciona Modo:${NC}"
echo "1) MODO AUTO (Máxima calidad MP3 320kbps + Todo automático)"
echo "2) MODO AVANZADO (Personalizado)"
read -rp "Opción: " MODE

THREADS=$(nproc 2>/dev/null || echo 2)
META_OPTS="--embed-thumbnail --embed-metadata"

if [ "$MODE" = "1" ]; then
    FORMAT_OPTS="-x --audio-format mp3 --audio-quality 0"
    F_NAME="MP3 320k"
else
    echo -e "\n${YELLOW}Perfiles:${NC}"
    echo "1) Opus (Rápido) | 2) M4A (Móvil) | 3) FLAC (Lossless) | 4) MP3"
    read -rp "Formato: " PROFILE
    case "$PROFILE" in
        1) FORMAT_OPTS="-f bestaudio[ext=opus]"; F_NAME="Opus" ;;
        2) FORMAT_OPTS="-f bestaudio[ext=m4a]"; F_NAME="M4A" ;;
        3) FORMAT_OPTS="-x --audio-format flac"; F_NAME="FLAC" ;;
        *) FORMAT_OPTS="-x --audio-format mp3 --audio-quality 2"; F_NAME="MP3" ;;
    esac
    read -rp "¿Metadatos completos? [S/n]: " M
    [[ "$M" =~ ^[Nn]$ ]] && META_OPTS=""
fi

# ================= 5. Descarga =================
echo -e "\n${BLUE}Descargando $NEW archivos en $F_NAME...${NC}\n"

yt-dlp \
    $FORMAT_OPTS \
    -N "$THREADS" \
    $META_OPTS \
    --download-archive "$ARCHIVE" \
    --no-overwrites \
    --parse-metadata "title:%(artist)s - %(title)s" \
    -o "$PLAYLIST_DIR/%(title).200s.%(ext)s" \
    "$URL"

echo -e "\n${GREEN}✔ ¡Finalizado! Ubicación:${NC} $PLAYLIST_DIR"