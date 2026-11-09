# Luchtmeetnet for Home Assistant

Air quality from the official Dutch measuring network [Luchtmeetnet](https://www.luchtmeetnet.nl) (RIVM, GGD Amsterdam, DCMR and the provinces), with the full measurement history in your statistics.

## What you get

- One device per station, with a sensor for every component the station measures: PM2.5, PM10, NO₂, NO, O₃, SO₂, CO, NOx, NH₃, benzene and so on, plus the Dutch air quality index (LKI).
- **History import.** When you add a station you choose how many years of history to import. The measured hourly values are written into the long-term statistics of the new sensors, in the background, so a statistics graph shows years of data from day one. The import resumes after a restart. Use the action `luchtmeetnet.import_history` to import a different period later.
- **Correct hourly statistics.** Luchtmeetnet publishes an hour's value roughly an hour after it ends, and sometimes later. On every update the integration rewrites the statistics of the last 48 hours with the published values, so each value sits in the hour it was measured and late data fills gaps. You can switch this off in the options.

Values are hourly averages in µg/m³ and are not validated; RIVM validates the data afterwards.

## Installation

In Home Assistant 2026.11 or later: **Settings → Marketplace → Add from link**, paste `https://github.com/gerritjandebruin/ha-luchtmeetnet` and install. Restart, then add the integration under **Settings → Devices & services → Add integration → Luchtmeetnet**.

Manually: copy `custom_components/luchtmeetnet` into your `config/custom_components/` and restart.

## Notes

- The API rate limits requests. A history import therefore takes a while: about a minute per year of data per station.
- The history import overwrites existing hourly statistics of the sensors for the imported period with the measured values. Short-term (5-minute) statistics are not touched.
- Data: [Luchtmeetnet open API](https://api-docs.luchtmeetnet.nl/). This integration is not affiliated with Luchtmeetnet or RIVM.

## License

MIT
