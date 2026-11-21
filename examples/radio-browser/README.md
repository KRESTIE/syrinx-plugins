# Radio Browser

Thousands of live radio stations from [radio-browser.info](https://www.radio-browser.info), a free, community-run
directory. A complete example of a "source" plugin with the Python SDK: home rows by genre, search, station pages,
live streams, and a setting (your country) that adds a row once it is set.

```sh
python3 plugin.py            # http://localhost:8701/manifest.json
```

The station list belongs to Radio Browser (Open Database License); the streams belong to each station. The plugin
sends a descriptive User-Agent and reports each play to Radio Browser, as its API asks. Stream addresses are absolute:
the device connects to each radio directly.
