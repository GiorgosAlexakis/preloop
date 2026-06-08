# Publishing Runtime Plugins

This guide covers publishing the standalone Preloop runtime plugins without
requiring the Preloop CLI on the target machine. The CLI can still provision
Agent Control config, but marketplace installation and runtime verification
must work from the agent runtime alone.

## Release Preconditions

- Bump matching versions in:
  - `openclaw-preloop/package.json`
  - `openclaw-preloop/openclaw.plugin.json`
  - `hermes-preloop/pyproject.toml`
  - `hermes-preloop/preloop-plugin.json`
- Confirm the package names are final:
  - npm/OpenClaw: `@preloop/openclaw-plugin`
  - PyPI/Hermes: `preloop-hermes-plugin`
- Confirm each README includes CLI-free manual testing instructions.
- Run the runtime plugin tests:

```bash
cd preloop
pytest runtime-plugins/tests
```

## OpenClaw Plugin

Build and validate the npm package:

```bash
cd preloop/runtime-plugins/openclaw-preloop
npm ci
npm run build
npm pack --dry-run
npm publish --access public --dry-run
```

Publish to npm:

```bash
npm publish --access public
```

After npm publishing, submit the same package metadata to the OpenClaw plugin
marketplace using `openclaw.plugin.json`. The marketplace entry should install
the npm package and run:

```bash
preloop-openclaw-plugin verify --config ~/.openclaw/config.json
```

Manual smoke test on a machine without the Preloop CLI:

```bash
openclaw plugins install @preloop/openclaw-plugin
preloop-openclaw-plugin verify --config ~/.openclaw/openclaw.json
preloop-openclaw-plugin run --config ~/.openclaw/openclaw.json
```

Marketplace UX requirement: if the OpenClaw config does not already contain
`plugins.entries.openclaw-plugin.config`, the marketplace installer or a
separate Preloop connect helper must prompt the user to log in or sign up to
Preloop in a browser. Keep this OAuth/token bootstrap outside the runtime
extension entrypoint because OpenClaw blocks extension bundles that combine
environment access with credential-bearing network requests. The bootstrap
should use the existing OAuth CLI flow (`client_id=cli`,
`redirect_uri=urn:ietf:wg:oauth:2.0:oob`) to obtain a Preloop API token, call the
runtime-session bootstrap endpoint for the current OpenClaw runtime, then write
`plugins.entries.openclaw-plugin.config` with the generated runtime bearer
token. Users should never have to hand-author runtime bearer tokens.

## Hermes Plugin

Build and validate the Python package:

```bash
cd preloop/runtime-plugins/hermes-preloop
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m pip install --force-reinstall dist/*.whl
preloop-hermes-plugin verify --config ~/.hermes/config.yaml
```

Publish to PyPI:

```bash
python -m twine upload dist/*
```

After PyPI publishing, submit `preloop-plugin.json` to the Hermes plugin
marketplace. The marketplace entry should install the PyPI package and run:

```bash
preloop-hermes-plugin verify --config ~/.hermes/config.yaml
```

Manual smoke test on a machine without the Preloop CLI:

```bash
hermes plugins install preloop-hermes-plugin
preloop-hermes-plugin login --config ~/.hermes/config.yaml
preloop-hermes-plugin verify --config ~/.hermes/config.yaml
preloop-hermes-plugin run --config ~/.hermes/config.yaml
```

Marketplace UX requirement: if `~/.hermes/config.yaml` does not already contain
`preloop.control`, the plugin must prompt the user to log in or sign up to
Preloop in a browser. The standalone helper should use the existing OAuth CLI
flow (`client_id=cli`, `redirect_uri=urn:ietf:wg:oauth:2.0:oob`) to obtain a
Preloop API token, call the runtime-session bootstrap endpoint for the current
Hermes runtime, then write `preloop.control` with the generated runtime bearer
token. Users should never have to hand-author runtime bearer tokens.
