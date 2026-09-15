# Travel Guide HTML

Research and build Chinese travel guides with daily itineraries, linked route
maps, source references and offline HTML delivery. Supports revising an existing
guide while preserving confirmed preferences and manual route choices.

## Recommended installation

From the repository root with Node.js **22.16+**:

```sh
node --experimental-strip-types scripts/install-skill.ts travel-guide-html --mode copy
```

Add `--agent pi` for Pi, or use `--mode link` for development in this checkout.
Open a new client session and ask it to use `travel-guide-html`. Repeat the
command with `--replace` to update a copy. See the source checkout's
`docs/installing-skills.md` for destinations, verification and removal.

## Dependencies and use

The static checker requires Python 3 and uses only its standard library.
Travel research requires available web search tools; interactive and visual QA
requires a browser and image-viewing capability. No specific research plugin
is required. Installation does not install these external tools.

Read [SKILL.md](SKILL.md) for the workflow. From the installed skill directory:

```sh
python3 scripts/check_offline_html.py /absolute/path/guide.html --strict-offline
```

This checks static IDs, fragment references and resource dependencies; it does
not execute JavaScript or prove mobile, browser or print behavior. Offline
sharing applies to the produced guide; current travel research still needs
online evidence. Deployment and bookings are separate, explicitly authorized
operations.

## Origin

Imported from the local `iCloud/tours` project's
`.agents/skills/travel-guide-html/`. The included Qiandaohu retrospective is a
historical workflow example, not current travel advice. Original trip HTML,
photos, project notes and the separate deployment skill are not bundled.
