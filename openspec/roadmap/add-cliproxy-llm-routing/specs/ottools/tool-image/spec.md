## MODIFIED Requirements

### Requirement: Configuration via `tools.image` block

The `ot_image` pack SHALL be configurable via `onetool.yaml` under
`tools.ot_image`. Its `llm` selection SHALL control generation for `image.ask()` and
`image.summary()`, while image processing settings SHALL remain pack-level fields.

#### Scenario: model required for ask and summary

- **WHEN** no model is supplied by the call, `tools.ot_image.llm`, or top-level `llm`
- **AND** `image.ask()` or `image.summary()` is called
- **THEN** it SHALL return an error string, not raise, indicating a generation model is required

#### Scenario: Inherit generation selection from top-level llm config

- **WHEN** a generation field is not set under `tools.ot_image.llm`
- **THEN** `image` SHALL inherit that field from the top-level `llm` configuration
- **AND** a CLIProxyAPI route SHALL use its inference client credential without requiring `OPENAI_API_KEY`

#### Scenario: Per-call model and effort override

- **WHEN** `image.ask()` or `image.summary()` is called with `model="terra"` and `effort="high"`
- **THEN** the operation SHALL resolve `terra` from the shared registry and request high effort
- **AND** the selected model SHALL be validated for image input before network I/O

#### Scenario: max_edge override

- **WHEN** `tools.ot_image.max_edge: 800` is set in config
- **AND** `image.load(img="~/large.png")` is called with a 2000×1500px image
- **THEN** the model-upload bytes SHALL be resized to fit within 800px on the long edge

