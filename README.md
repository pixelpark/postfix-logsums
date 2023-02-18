# postfix-logsums - Postfix log entry summarizer

Copyright © 2023 by Frank Brehm <frank@brehm-online.com>, Berlin, Germany

## Description

Postfix-logsums is a log analyzer/summarizer for the Postfix MTA.

It provides both a Python module `postfix_logsums` as well as the executable
script `postfix-logsums` based on the latter module. The Python module may be
used as an API.

This software was inspired by the Perl script `pflogsumm.pl` by James S. Seymour
`http://jimsun.linxnet.com/postfix_contrib.html`.

It is designed to provide an over-view of Postfix activity, with just enough
detail to give the administrator a "heads up" for potential trouble spots.

It generates summaries and, if demanded, detailed reports of mail server traffic
ovolumes, rejected and bounced email, and server warnings, errors and panics.

## Requirements

The module and the script are needing Python >= 3.5 without any nono-standard
libraries.

## License

This package is licensed by the LGPL 3.


