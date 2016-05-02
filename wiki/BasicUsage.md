Basic Usage
===

<!-- MarkdownTOC -->

1. [Manual calculation of stats for a month \(via `cURL`\)](#manual-calculation-of-stats-for-a-month-via-curl)
    1. [Examples for April 2016 usage](#examples-for-april-2016-usage)

<!-- /MarkdownTOC -->

<a name="manual-calculation-of-stats-for-a-month-via-curl"></a>
## Manual calculation of stats for a month (via `cURL`)

Base URL: `http://<version>.tools-usagestats.vertnet-portal.appspot.com/admin/parser/`

Command: `init`

Method: `POST`

Parameters (**bold** means mandatory):

- **`period`**: YYYYMM of the period to process (*i.e.*, the month we want to calculate usage stats). For example, 201603 for March 2016 usage stats
- `force`: true/false, wheter or not it should override existing data for the given period. Defaults to False
- `testing`: true/false, whether or not use the `jotegui/statReports` testing repository instead of actual publishers' ones to store reports and send issues. Defaults to False
- `github_store`: true/false, whether or not store a txt version of the reports on the publishers' (or the testing) GitHub repositories. Defaults to False
- `github_issue`: true/false, whether or not create a new issue to notify of the report on the publishers' (or the testing) GitHub repositories. Defaults to False

<a name="examples-for-april-2016-usage"></a>
### Examples for April 2016 usage

* Basic: No override, no testing, no GitHub process

```sh
curl -i -X POST -d "period=201604" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```

* Overriding an existing period

```sh
curl -i -X POST -d "period=201604&force=true" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```

* Storing on GitHub and sending notification issue

```sh
curl -i -X POST -d "period=201604&github_store=true&github_issue=true" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```