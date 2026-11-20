### AMC Tracker

Maintained assets, their annual maintenance contracts (AMC), warranty and service visits, linked to each other and to the existing
Work Order Contract and the ERPNext purchase documents. Works on Frappe / ERPNext v15 and v16 (it uses only long-standing APIs).

Open it at `/app/amc_tracker` (the page: dashboard, assets, contracts, visits, reports). The same three DocTypes
(`AMC Asset`, `AMC Contract`, `AMC Visit`) are also normal desk forms and lists.

#### What is in it

| DocType | Naming | Notes |
| --- | --- | --- |
| AMC Asset | `LFT-.###`, `RO-.###`, `DG-.###`, `AC-.###`, `FIRE-.###`, `CCTV-.###`, `ELE-.###`, `UPS-.###`, `PMP-.###`, `IT-.###`, `AST-.###` by asset type | warranty, purchase details (fetched from a Purchase Order / Invoice), computed AMC and visit fields, cost of ownership, track changes |
| AMC Contract | `AMC-.YYYY.-.####` (submittable) | child table `AMC Contract Asset`; one contract can cover several assets; Generate Visit Schedule and Create Renewal |
| AMC Visit | `VIS-.YYYY.-.#####` | planned and done visits; saving a visit refreshes the asset's last and next visit |

The rules (status days, schedule dates, renewal values, cost of ownership) are in `amc_tracker/logic.py` and have unit tests.

#### Install (on a live bench: ask before each step)

The order matters. Running `install-app` on a live bench without the symlink makes every page fail until the next restart.

1. Copy the app folder to `~/frappe-bench/apps/amc_tracker` (nothing changes for the running site).
2. Give the running workers a path to the new package: `ln -s ../apps/amc_tracker/amc_tracker sites/amc_tracker`
3. `./env/bin/pip install -e apps/amc_tracker` and add `amc_tracker` to `sites/apps.txt` (keep a backup of `apps.txt`).
4. `bench --site <site> install-app amc_tracker` (creates the roles, syncs the doctypes and the page).
5. `bench --site <site> migrate` if you change a DocType later.
6. Restart the bench yourself (supervisor / systemd). After that the symlink in step 2 is no longer needed.

Run the rule tests anywhere (no site needed): `python -m unittest amc_tracker.tests.test_logic`

#### Reports

Asset Coverage, Renewals Due and Visit Schedule show the table with the filters you picked and download it as an Excel file
(`.xlsx`, made by `amc_tracker/export.py`).

#### Dropdowns

Every dropdown opens a search box. Where a dropdown has an **Other** option (asset type, visit type), choosing it shows a box to type
what it is; the text is kept in `asset_type_other` / `visit_type_other` and shown next to the type in lists and reports.

#### Roles

* **AMC Manager**: full access; submits and cancels contracts; receives the daily alerts.
* **Maintenance User** (the standard ERPNext role): creates and edits visits, reads assets and contracts.
* **Campus Viewer**: read only. Limit a user to a campus with a **User Permission on Company**; assets, contracts and visits
  (through the assets they cover) are then limited to that campus.

#### Daily job

`amc_tracker.tasks.daily` runs every night (needs the scheduler on):

1. recomputes status and days left on every asset, contract and visit;
2. sends one system notification per AMC Manager (Frappe also e-mails it, following each user's Notification Settings) for
   * a contract ending within `remind_before_days`: first at that many days left, then again at 30, 7 and 0;
   * a warranty ending within 60 days (at 60, 30, 7 and 0);
   * visits planned in the next 3 days, and overdue visits (every day until done).

The page shows the same things live: a "Needs attention" strip at the top of the dashboard and a bell in the top bar.

#### Add a new asset type

1. Add the type and its series prefix to `ASSET_TYPE_PREFIX` in `amc_tracker/logic.py` (a type that is not listed uses `AST`).
2. Add the type to the options of the field *Asset type* in `amc_tracker/amc_tracker/doctype/amc_asset/amc_asset.json`.
3. Run `bench --site <site> migrate`. The page picks the new type up by itself.

#### Starting records

`amc_tracker/seed.py` can create the 4 sample assets and 3 contracts, but only where the Company and Supplier already exist:

```
bench --site <site> execute amc_tracker.seed.run
bench --site <site> execute amc_tracker.seed.run --kwargs '{"dry_run": 0}'
```

#### Not included

Workspace shortcuts, number cards, the desk Script Reports and a timeline page are not part of this version: the page covers the
dashboard and the three reports.

#### License

mit
