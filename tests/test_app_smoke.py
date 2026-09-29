from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_default_app_renders_without_runtime_exceptions():
    app = AppTest.from_file("../app.py", default_timeout=20).run()

    assert not app.exception
    assert any("Ammonia Loop Lab" in block.value for block in app.markdown)
    assert len(app.metric) == 5
    assert app.metric[0].label == "Annualized cost"
    assert len(app.tabs) == 3
    assert len(app.selectbox) == 2
    assert app.selectbox[0].label == "X-axis input"
    assert app.selectbox[1].label == "Model output"
    assert app.button[0].label == "Reset inputs to defaults"
    assert not app.download_button
    number_input_labels = {widget.label for widget in app.number_input}
    assert "Plant lifetime (years)" in number_input_labels
    assert "Ref. cost (M$)" not in number_input_labels
    assert not any("Operating summary" in block.value for block in app.markdown)
    assert not any("Reactor-inlet composition" in block.value for block in app.markdown)
    assert not any("Teaching model" in caption.value for caption in app.caption)
    assert any("All unit" in message.value for message in app.success)


def test_zero_purge_with_positive_argon_shows_infeasible_state():
    app = AppTest.from_file("../app.py", default_timeout=20).run()
    app.slider(key="purge_fraction_pct").set_value(0.0).run()

    assert not app.exception
    assert any("Infeasible steady state" in message.value for message in app.error)
    assert any("denominator" in message.value for message in app.info)
