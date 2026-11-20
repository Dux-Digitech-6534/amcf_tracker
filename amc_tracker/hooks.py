app_name = "amc_tracker"
app_title = "AMC Tracker"
app_publisher = "Dux Digitech"
app_description = "Annual maintenance contracts, warranty and service visits for maintained assets"
app_email = "durgesh.joshi@thesvsgroup.org"
app_license = "mit"

# Roles exist before the doctypes and the page that use them are synced
before_install = "amc_tracker.install.before_install"
after_install = "amc_tracker.install.after_install"

# Contracts and visits are limited to the user's campus (through the assets they cover)
permission_query_conditions = {
	"AMC Contract": "amc_tracker.permissions.contract_query",
	"AMC Visit": "amc_tracker.permissions.visit_query",
}
has_permission = {
	"AMC Contract": "amc_tracker.permissions.contract_has_permission",
	"AMC Visit": "amc_tracker.permissions.visit_has_permission",
}

# Recompute statuses and mail the AMC Managers every night
scheduler_events = {
	"daily": ["amc_tracker.tasks.daily"],
}
