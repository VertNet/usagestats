Basic Usage
===

<!-- MarkdownTOC -->

1. [Overview](#overview)
2. [Dataset information setup](#dataset-information-setup)
    1. [Example:](#example)
3. [Repository name consistency check](#repository-name-consistency-check)
4. [Manual calculation of stats for a month](#manual-calculation-of-stats-for-a-month)
    1. [Examples for April 2016 usage](#examples-for-april-2016-usage)
        1. [Default usage: No override, no testing, no GitHub process](#default-usage-no-override-no-testing-no-github-process)
        2. [Overriding an existing period](#overriding-an-existing-period)
        3. [Storing on GitHub and sending notification issue](#storing-on-github-and-sending-notification-issue)
        4. [Using a custom table](#using-a-custom-table)
2. [Restart after failure](#restart-after-failure)
    3. [Scenario 1, failed in the middle of storing issues on GitHub](#scenario-1-failed-in-the-middle-of-storing-issues-on-github)

<!-- /MarkdownTOC -->

<a name="overview"></a>
## Overview

Base URL: `http://<version>.tools-usagestats.vertnet-portal.appspot.com/`

Currently available versions:

* `prod`
* `dev`

How to build URLs properly:

    <Base URL>/<family>/<command>

<a name="dataset-information-setup"></a>
## Dataset information setup

Needed to ensure consistency and proper functioning. The process of extracting the reports relies on having information of all datasets already in the datastore.

Family: `admin/setup`

Command: `datasets`

Method: `POST`

Parameters (**bold** means mandatory): None

<a name="example"></a>
### Example:

```sh
curl -i -X POST -d "" http://tools-usagestats.vertnet-portal.appspot.com/admin/setup/datasets
```

<a name="repository-name-consistency-check"></a>
## Repository name consistency check

Needed to ensure consistency and proper functioning. Resource repositories on GitHub must be properly and uniquely referenced to in the CartoDB registry table. Otherwise, the application won't be able to adequately store the report or send a notification issue.

Family: `admin/tools`

Command: `repo_checker`

Method: `GET` or `POST`

Parameters (**bold** means mandatory): None

Example:

```sh
curl -i -X GET http://tools-usagestats.vertnet-portal.appspot.com/admin/tools/repo_checker
```

Result: If successful, a JSON-like message; `{"result": "success"}`. Otherwise, a list of all the mismatching repository/resource names

<a name="manual-calculation-of-stats-for-a-month"></a>
## Manual calculation of stats for a month

Family: `admin/parser`

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

<a name="restart-after-failure"></a>
## Restart after failure

Thanks to the modular structure of the application, one can easily restart the process at almost any point without pain. Each step has its own request handler that can be called directly passing the required parameters. Besides, for long-running tasks like storing all reports on GitHub, the process enters a loop that processes batches of reports until it finishes or receives a DeadlineExceededError from App Engine. In the latter case, it respawns taking the last (unfinished) batch of reports.

<a name="scenario-1-failed-in-the-middle-of-storing-issues-on-github"></a>
### Scenario 1, failed in the middle of storing issues on GitHub

Let's assume you forgot to call the `datasets` setup process and launched the main task with an incomplete collection of dataset information. This is what would likely happen:

* `init` would end successfully
* `get_events` would end successfully, extracting the events to parse
* `process_events` would end successfully, storing the reports in the datastore
* `github_store` would **fail** eventually, when trying to get info from a dataset that is not in the datastore. The process will halt here.

At this point, you have all reports in the datastore, some of them with the `stored` property set to `True` and others (the ones after and including the one that failed) set to `False`, and all of them with the `issue_sent` property set to `False` (since this process did not execute yet). The correct way to proceed is as follows:

1. Make a request to the [datasets setup handler](#dataset-information-setup) so that the missing data are uploaded to the datastore
2. Make a request to the `github_store` endpoint, passing these two parameters exactly as you wrote them for the `init` request:
    * `period`
    * `github_issue`

The task will restart from the `github_store` endpoint and will process only those reports with `store = False`. After that, it will continue as usual depending on the value of the `github_issue` variable.