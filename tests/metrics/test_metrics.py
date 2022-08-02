from parameterized import parameterized, param
from unittest import TestCase
from mock import MagicMock
from samtranslator.metrics.metrics import (
    Metrics,
    MetricsPublisher,
    CWMetricsPublisher,
    DummyMetricsPublisher,
    Unit,
    MetricDatum,
)


class MetricPublisherTestHelper(MetricsPublisher):
    def __init__(self):
        MetricsPublisher.__init__(self)
        self.metrics_cache = []
        self.namespace = ""

    def publish(self, namespace, metrics):
        self.namespace = namespace
        self.metrics_cache = metrics


class TestMetrics(TestCase):
    @parameterized.expand(
        [
            param(
                "DummyNamespace",
                "CountMetric",
                12,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "IAMError",
                59,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
        ]
    )
    def test_publishing_count_metric(self, namespace, name, value, dimensions):
        mock_metrics_publisher = MetricPublisherTestHelper()
        metrics = Metrics(namespace, mock_metrics_publisher)
        metrics.record_count(name, value, dimensions)
        metrics.publish()
        self.assertEqual(len(mock_metrics_publisher.metrics_cache), 1)
        published_metric = mock_metrics_publisher.metrics_cache[0].get_metric_data()
        self.assertEqual(published_metric["MetricName"], name)
        self.assertEqual(published_metric["Dimensions"], dimensions)
        self.assertEqual(published_metric["Value"], value)

    @parameterized.expand(
        [
            param(
                "DummyNamespace",
                "SARLatency",
                1200,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "IAMLatency",
                400,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
        ]
    )
    def test_publishing_latency_metric(self, namespace, name, value, dimensions):
        mock_metrics_publisher = MetricPublisherTestHelper()
        metrics = Metrics(namespace, mock_metrics_publisher)
        metrics.record_latency(name, value, dimensions)
        metrics.publish()
        self.assertEqual(len(mock_metrics_publisher.metrics_cache), 1)
        published_metric = mock_metrics_publisher.metrics_cache[0].get_metric_data()
        self.assertEqual(published_metric["MetricName"], name)
        self.assertEqual(published_metric["Dimensions"], dimensions)
        self.assertEqual(published_metric["Value"], value)

    @parameterized.expand(
        [
            param(
                "DummyNamespace",
                "CountMetric",
                12,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "LatencyMetric",
                1200,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
        ]
    )
    def test_publishing_metric_without_calling_publish(self, namespace, name, value, dimensions):
        mock_metrics_publisher = MetricPublisherTestHelper()
        metrics = Metrics(namespace, mock_metrics_publisher)
        metrics.record_count(name, value, dimensions)
        del metrics
        self.assertEqual(len(mock_metrics_publisher.metrics_cache), 1)
        published_metric = mock_metrics_publisher.metrics_cache[0].get_metric_data()
        self.assertEqual(published_metric["MetricName"], name)
        self.assertEqual(published_metric["Dimensions"], dimensions)
        self.assertEqual(published_metric["Value"], value)


class TestCWMetricPublisher(TestCase):
    @parameterized.expand(
        [
            param(
                "DummyNamespace",
                "CountMetric",
                12,
                Unit.Count,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "IAMError",
                59,
                Unit.Count,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "SARLatency",
                1200,
                Unit.Milliseconds,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
            param(
                "DummyNamespace",
                "IAMLatency",
                400,
                Unit.Milliseconds,
                [{"Name": "SAM", "Value": "Dim1"}, {"Name": "SAM", "Value": "Dim2"}],
            ),
        ]
    )
    def test_publish_metric(self, namespace, name, value, unit, dimensions):
        mock_cw_client = MagicMock()
        metric_publisher = CWMetricsPublisher(mock_cw_client)
        metric_datum = MetricDatum(name, value, unit, dimensions)
        metrics = [metric_datum]
        metric_publisher.publish(namespace, metrics)
        call_kwargs = mock_cw_client.put_metric_data.call_args.kwargs
        published_metric_data = call_kwargs["MetricData"][0]
        self.assertEqual(call_kwargs["Namespace"], namespace)
        self.assertEqual(published_metric_data["MetricName"], name)
        self.assertEqual(published_metric_data["Unit"], unit)
        self.assertEqual(published_metric_data["Value"], value)
        self.assertEqual(published_metric_data["Dimensions"], dimensions)

    @parameterized.expand(
        [
            param("DummyNamespace", "CountMetric", 12, Unit.Count, []),
        ]
    )
    def test_publish_more_than_20_metrics(self, namespace, name, value, unit, dimensions):
        mock_cw_client = MagicMock()
        metric_publisher = CWMetricsPublisher(mock_cw_client)
        single_metric = MetricDatum(name, value, unit, dimensions)
        total_metrics = 45
        metrics_list = [single_metric for _ in range(total_metrics)]
        metric_publisher.publish(namespace, metrics_list)
        call_args_list = mock_cw_client.put_metric_data.call_args_list

        self.assertEqual(mock_cw_client.put_metric_data.call_count, 3)
        # Validating that metrics are published in batches of 20
        self.assertEqual(len(call_args_list[0].kwargs["MetricData"]), min(total_metrics, metric_publisher.BATCH_SIZE))
        total_metrics -= metric_publisher.BATCH_SIZE
        self.assertEqual(len(call_args_list[1].kwargs["MetricData"]), min(total_metrics, metric_publisher.BATCH_SIZE))
        total_metrics -= metric_publisher.BATCH_SIZE
        self.assertEqual(len(call_args_list[2].kwargs["MetricData"]), min(total_metrics, metric_publisher.BATCH_SIZE))

    def test_do_not_fail_on_cloudwatch_any_exception(self):
        mock_cw_client = MagicMock()
        mock_cw_client.put_metric_data = MagicMock()
        mock_cw_client.put_metric_data.side_effect = Exception("BOOM FAILED!!")
        metric_publisher = CWMetricsPublisher(mock_cw_client)
        single_metric = MetricDatum("Name", 20, Unit.Count, [])
        metric_publisher.publish("SomeNamespace", [single_metric])
        self.assertTrue(True)

    def test_for_code_coverage(self):
        dummy_publisher = DummyMetricsPublisher()
        dummy_publisher.publish("NS", [None])
        self.assertTrue(True)
