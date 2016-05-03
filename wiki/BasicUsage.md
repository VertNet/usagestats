Basic Usage
===

<!-- MarkdownTOC -->

1. [Dataset information setup](#dataset-information-setup)
    1. [Example:](#example)
2. [Manual calculation of stats for a month](#manual-calculation-of-stats-for-a-month)
    1. [Examples for April 2016 usage](#examples-for-april-2016-usage)
        1. [Default usage: No override, no testing, no GitHub process](#default-usage-no-override-no-testing-no-github-process)
        2. [Overriding an existing period](#overriding-an-existing-period)
        3. [Storing on GitHub and sending notification issue](#storing-on-github-and-sending-notification-issue)
        4. [Using a custom table](#using-a-custom-table)

<!-- /MarkdownTOC -->

<a name="dataset-information-setup"></a>
## Dataset information setup

Needed to ensure consistency and proper functioning. The process of extracting the reports relies on having information of all datasets already in the datastore.

Base URL: `http://<version>.tools-usagestats.vertnet-portal.appspot.com/admin/setup/`

Command: `datasets`

Method: `POST`

Parameters (**bold** means mandatory): None

<a name="example"></a>
### Example:

```sh
curl -i -X POST -d "" http://tools-usagestats.vertnet-portal.appspot.com/admin/setup/datasets
```

<a name="manual-calculation-of-stats-for-a-month"></a>
## Manual calculation of stats for a month

Base URL: `http://<version>.tools-usagestats.vertnet-portal.appspot.com/admin/parser/`

Command: `init`

Method: `POST`

Parameters (**bold** means mandatory):

- **`period`**: YYYYMM of the period to process (*i.e.*, the month we want to calculate usage stats). For example, 201603 for March 2016 usage stats
- `force`: true/false, wheter or not it should override existing data for the given period. Defaults to False
- `testing`: true/false, whether or not use the `jotegui/statReports` testing repository instead of actual publishers' ones to store reports and send issues. Defaults to False
- `github_store`: true/false, whether or not store a txt version of the reports on the publishers' (or the testing) GitHub repositories. Defaults to False
- `github_issue`: true/false, whether or not create a new issue to notify of the report on the publishers' (or the testing) GitHub repositories. Defaults to False
- `table_name`: Name of the CartoDB table to query in order to extract usage data. Defaults to `query_log_master`. *Note*: time-constraints will **not** be applied if a table name is provided here (unless it's the same as the default value). Therefore, the table with the given name **must exist and must have all and nothing but the needed records**.

<a name="examples-for-april-2016-usage"></a>
### Examples for April 2016 usage

<a name="default-usage-no-override-no-testing-no-github-process"></a>
#### Default usage: No override, no testing, no GitHub process

```sh
curl -i -X POST -d "period=201604" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```

<a name="overriding-an-existing-period"></a>
#### Overriding an existing period

```sh
curl -i -X POST -d "period=201604&force=true" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```

<a name="storing-on-github-and-sending-notification-issue"></a>
#### Storing on GitHub and sending notification issue

```sh
curl -i -X POST -d "period=201604&github_store=true&github_issue=true" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```

<a name="using-a-custom-table"></a>
#### Using a custom table

```sh
curl -i -X POST -d "period=201604&table_name=query_log_201604" http://tools-usagestats.vertnet-portal.appspot.com/admin/parser/init
```
