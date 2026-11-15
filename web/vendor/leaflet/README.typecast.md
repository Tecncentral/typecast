# Leaflet 1.9.4

Vendored from the public npm release. JavaScript, CSS and rendered image pixels
are unchanged; the PNG files carry added origin metadata for Impeccable:
https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz

Upstream: https://leafletjs.com/ and https://github.com/Leaflet/Leaflet/tree/v1.9.4

License: BSD 2-Clause, reproduced in `LICENSE`.

Archive SHA-256: `84c65a256e50657896f54c33bd857b6849ebe94c817803be818bf32a3dde0b77`

`leaflet-src.esm.js` is the upstream readable ES module distribution. Its source
map and the stylesheet's image dependencies are included locally. Typecast's map
module imports this file directly; no CDN script or stylesheet is used at runtime.
The optional street basemap requests OpenStreetMap tiles. If those requests fail,
Typecast retains coordinate pins and displays the supplied local aerial evidence.
