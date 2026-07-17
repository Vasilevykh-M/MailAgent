# CLI reference

All global options precede the command:

```bash
yandex-drive --env .env --verbose diagnose
```

Commands:

```bash
yandex-drive auth
yandex-drive auth --force
yandex-drive diagnose
yandex-drive metadata /photos
yandex-drive metadata /archive/data.bin --json
yandex-drive download disk:/archive/data --output ./downloads/data
yandex-drive download /reports/report.xlsx --output ./downloads/report.xlsx --overwrite
yandex-drive upload ./archive.zip /backups/archive.zip --overwrite
yandex-drive upload ./data disk:/archive/data --json
```

`--json` writes only JSON to standard output. Status `0` means success, `1`
denotes a typed SDK error, and `2` is reserved for invalid argparse input.
Expected errors go to standard error. `--debug` enables a traceback; `--verbose`
enables safe progress logging. Diagnostics report only settings and token state,
not any secret or token value.

A completed download reports its final local path and byte count. A completed
upload reports remote path, resource name, and size when the API supplies one.
