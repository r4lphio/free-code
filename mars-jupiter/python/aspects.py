"""Mars-Jupiter aspect dates from NASA JPL's DE440s ephemeris, computed with Skyfield.

Positions are geocentric, apparent, in ecliptic longitude of date (the tropical zodiac astrologers use).
The separation is (Mars - Jupiter) mod 360. An aspect is exact when the separation crosses one of these angles:

    conjunction 0, sextile 60 and 300, square 90 and 270, trine 120 and 240, opposition 180

Mars can turn retrograde near an aspect, so one aspect can be exact two or three times in a few weeks. Each
crossing is listed; the "hit" column numbers them (1, 2, 3) within one pass.

Usage: python aspects.py <de440s.bsp> <out.csv> [--start 1990-01-01] [--end 2036-01-01]
If the .bsp file is not there, Skyfield downloads it (32 MB) from NASA's NAIF server into that folder.
Writes one row per exact crossing: utc time, date, aspect, angle, hit, mars_lon, jupiter_lon, mars_speed.
Also writes <out>-daily.csv: the separation at 00:00 UTC each day (used for orbs).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from skyfield.api import Loader, load, load_file
from skyfield.framelib import ecliptic_frame

ASPECTS = {0: "conjunction", 60: "sextile", 90: "square", 120: "trine", 180: "opposition",
           240: "trine", 270: "square", 300: "sextile"}


def longitudes(eph, ts, t):
    """Geocentric apparent ecliptic longitude of date, degrees, for Mars and Jupiter at times t."""
    earth = eph["earth"]
    out = []
    # Barycenters: DE440s has no planet centres; Mars and its moons, and Jupiter and its moons, differ by metres.
    for body in ("mars barycenter", "jupiter barycenter"):
        lat, lon, _ = earth.at(t).observe(eph[body]).apparent().frame_latlon(ecliptic_frame)
        out.append(lon.degrees)
    return out[0], out[1]


def separation(eph, ts, t):
    m, j = longitudes(eph, ts, t)
    return (m - j) % 360.0


def crossings(eph, ts, start: str, end: str) -> pd.DataFrame:
    """Every exact crossing of an aspect angle, refined by bisection to under a second."""
    t0, t1 = ts.from_datetime(pd.Timestamp(start, tz="UTC")), ts.from_datetime(pd.Timestamp(end, tz="UTC"))
    jd = np.arange(t0.tt, t1.tt, 0.25)  # every 6 hours; the separation moves under 1 degree a day
    t = ts.tt_jd(jd)
    sep = separation(eph, ts, t)
    rows = []
    for angle, name in ASPECTS.items():
        d = (sep - angle + 180.0) % 360.0 - 180.0  # signed distance to the angle, -180..180
        idx = np.where((np.sign(d[:-1]) != np.sign(d[1:])) & (np.abs(d[:-1] - d[1:]) < 90))[0]
        for i in idx:
            lo, hi = jd[i], jd[i + 1]
            dlo = d[i]
            for _ in range(40):  # 6 hours / 2^40 is far below a second
                mid = (lo + hi) / 2
                dm = (separation(eph, ts, ts.tt_jd(mid)) - angle + 180.0) % 360.0 - 180.0
                if np.sign(dm) == np.sign(dlo):
                    lo, dlo = mid, dm
                else:
                    hi = mid
            tm = ts.tt_jd((lo + hi) / 2)
            m, j = longitudes(eph, ts, tm)
            m2, _ = longitudes(eph, ts, ts.tt_jd(tm.tt + 1))
            rows.append({"utc": tm.utc_datetime().replace(microsecond=0), "aspect": name, "angle": angle,
                         "mars_lon": round(float(m), 4), "jupiter_lon": round(float(j), 4),
                         "mars_speed": round(float((m2 - m + 180) % 360 - 180), 4)})
    df = pd.DataFrame(rows).sort_values("utc").reset_index(drop=True)
    df["utc"] = pd.to_datetime(df.utc, utc=True)
    df["date"] = df.utc.dt.strftime("%Y-%m-%d")
    # Number repeated crossings of the same angle within 120 days (a retrograde pass) as hits 1, 2, 3.
    hit = []
    last: dict[int, tuple[pd.Timestamp, int]] = {}
    for u, a in zip(df.utc, df.angle):
        prev = last.get(a)
        n = prev[1] + 1 if prev and (u - prev[0]).days < 120 else 1
        last[a] = (u, n)
        hit.append(n)
    df["hit"] = hit
    return df[["utc", "date", "aspect", "angle", "hit", "mars_lon", "jupiter_lon", "mars_speed"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bsp", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--start", default="1990-01-01")
    ap.add_argument("--end", default="2036-01-01")
    a = ap.parse_args()
    ts = load.timescale(builtin=True)
    eph = load_file(str(a.bsp)) if a.bsp.exists() else Loader(str(a.bsp.parent))(a.bsp.name)
    ev = crossings(eph, ts, a.start, a.end)
    ev.to_csv(a.out, index=False)
    days = pd.date_range(a.start, a.end, freq="D", tz="UTC", inclusive="left")
    sep = separation(eph, ts, ts.from_datetimes(list(days.to_pydatetime())))
    pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "separation": np.round(sep, 4)}).to_csv(
        a.out.with_name(a.out.stem + "-daily.csv"), index=False)
    print(f"{len(ev)} exact crossings from {a.start} to {a.end}")
    print(ev.aspect.value_counts().to_string())


if __name__ == "__main__":
    main()
