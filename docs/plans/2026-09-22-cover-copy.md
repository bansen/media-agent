# Cover copy from the final article

Scope: the user approved a small prompt change, not OCR or a new text renderer.

- [x] Generate a short cover headline and visual scene from the completed, channel-specific article. Require a supporting quote from the article, reject invalid output, and allow one LLM correction.
- [x] Build a fresh, text-free image prompt. Do not reuse the old planning prompt, article text, extracted headline, aspect ratio, or pixel dimensions in the image prompt.
- [x] Use the same preparation in one-click, individual cover generation, and CLI. Save the copy, supporting quote, article fingerprint, and actual prompt with the result.
- [x] Keep existing image size API parameters and delivery dimensions. Keep XHS backgrounds text-free because its existing renderer adds text.
- [x] Add regression tests for final-article grounding, prompt leakage, step prerequisites, workflow routing, and unchanged dimensions. Verify the complete test suite.

Limit: Image models can still produce accidental pseudo-text even when instructed not to. The extracted headline remains metadata for a future local overlay and is not sent to image generation. Users still review the image before publishing.
