.PHONY: render clean

# Render all PlantUML files to SVG
render:
	@echo "Rendering PlantUML diagrams to SVG..."
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker run --rm -v "$$(pwd):/work" -w /work plantuml/plantuml:1.2025.0 -tsvg -o rendered/ docs/architecture/*.puml; \
	elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then \
		podman run --rm -v "$$(pwd):/work" -w /work plantuml/plantuml:1.2025.0 -tsvg -o rendered/ docs/architecture/*.puml; \
	elif command -v plantuml >/dev/null 2>&1; then \
		cd docs/architecture && plantuml -tsvg -o rendered/ *.puml; \
	else \
		echo "Error: Neither Docker/Podman (running) nor plantuml CLI found. Please install one of them."; \
		exit 1; \
	fi
	@echo "✅ Diagrams rendered successfully to docs/architecture/rendered/"

# Clean rendered SVG files
clean:
	@echo "Cleaning rendered SVG files..."
	@rm -f docs/architecture/rendered/*.svg
	@echo "✅ Cleaned rendered SVG files"

