# Template attribution

The designs in this directory are ports of the resume templates in
[Resume Matcher](https://github.com/srbhr/Resume-Matcher), by the Resume Matcher
contributors, licensed under the Apache License, Version 2.0
(https://www.apache.org/licenses/LICENSE-2.0).

The Deedy design follows Debarghya Das's "Deedy Resume", also Apache-2.0, by way of
Resume Matcher's recreation.

Changes from the originals: rewritten from React components and CSS modules to one
Jinja page (`base.html.j2`) with per-design CSS; mirrored for right-to-left documents
with logical properties; system fonts only (the page's Content-Security-Policy loads
no fonts); and no letter-spacing, small caps, or opacity on text, which split or drop
glyphs in the PDF text layer an ATS reads.
