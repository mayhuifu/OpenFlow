from openflow.migrate.transformers import ConvertPublishResult, transform


def test_replaces_PublishResult_with_results_publish_and_TODO_comment():
    before = "self.PublishResult()\n"
    after = transform(before, ConvertPublishResult())
    assert "results.publish(" in after
    assert "TODO[openflow-migrate]" in after


def test_post_self_strip_form():
    before = "PublishResult()\n"
    after = transform(before, ConvertPublishResult())
    assert "results.publish(" in after
