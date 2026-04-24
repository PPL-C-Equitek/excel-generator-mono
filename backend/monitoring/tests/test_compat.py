from django.test import SimpleTestCase

import monitoring.contracts as legacy_contracts
import monitoring.views as legacy_views
from monitoring.domain.contracts import HealthCheck, MetricsRepository
from monitoring.interfaces.http import views as http_views


class MonitoringCompatibilityModuleTest(SimpleTestCase):
    def test_contracts_module_reexports_domain_contracts(self):
        self.assertIs(legacy_contracts.HealthCheck, HealthCheck)
        self.assertIs(legacy_contracts.MetricsRepository, MetricsRepository)

    def test_views_module_reexports_http_views(self):
        self.assertIs(legacy_views.live, http_views.live)
        self.assertIs(legacy_views.ready, http_views.ready)
        self.assertIs(legacy_views.stats, http_views.stats)
        self.assertIs(legacy_views.access, http_views.access)
