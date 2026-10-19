#!/bin/bash
# De qué rama sale una imagen: los scripts construyen desde el árbol de trabajo,
# esté en la rama que esté (el 14 oct se desplegó otra rama sin darnos cuenta).
# Se carga con `source` desde deploy-api.sh, deploy-front.sh y deploy-cluster.sh,
# que ya traen print_warning, BOLD y NC.
#
#   mostrar_rama_de <directorio del repo>
mostrar_rama_de() {
    local dir nombre rama detras
    if ! dir="$(cd "$1" 2>/dev/null && pwd)" || ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
        print_warning "No encuentro el repo en $1"
        return 0
    fi
    nombre="$(basename "$dir")"
    rama="$(git -C "$dir" symbolic-ref --short -q HEAD || echo "sin rama: $(git -C "$dir" rev-parse --short HEAD)")"
    echo -e "${BOLD:-}Rama:${NC:-}         $nombre en ${BOLD:-}${rama}${NC:-} ($(git -C "$dir" log -1 --format='%h %s' | cut -c1-60))"
    if [ "$rama" != "develop" ]; then
        print_warning "$nombre NO está en develop: la imagen saldrá de $rama"
    fi
    if [ -n "$(git -C "$dir" status --porcelain)" ]; then
        print_warning "Hay cambios sin commit en $nombre: pueden entrar en la imagen"
    fi
    detras="$(git -C "$dir" rev-list --count HEAD..origin/develop 2>/dev/null || echo 0)"
    if [ "$detras" != "0" ]; then
        print_warning "$nombre va $detras commits por detrás de origin/develop (según el último fetch)"
    fi
}
