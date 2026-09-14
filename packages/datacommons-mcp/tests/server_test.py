# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Protocol tests for client-controlled documentation guidance."""

import asyncio
from functools import partial

import pytest
from datacommons_mcp.app import DCApp
from datacommons_mcp.middleware import DOCUMENTATION_HEADER, DocumentationMiddleware
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_async
from mcp import McpError


@pytest.fixture
def documentation_app(monkeypatch, tmp_path, create_test_file):
    create_test_file("server.md", "Custom server instructions.\n")
    create_test_file("doc_instructions_extension.md", "Custom documentation hint.\n")
    monkeypatch.setenv("DC_INSTRUCTIONS_DIR", str(tmp_path))
    return DCApp


@pytest.mark.asyncio
@pytest.mark.parametrize("default", [False, True])
async def test_documentation_http_overrides(default, documentation_app, monkeypatch):
    monkeypatch.setenv("DC_ENABLE_DOCUMENTATION", str(default))
    app = documentation_app()
    server = app.mcp
    original = server.instructions
    monkeypatch.setattr(
        server, "run_http_async", partial(server.run_http_async, stateless_http=True)
    )

    @server.resource("test://unrelated")
    def unrelated():
        return "unchanged"

    async with run_server_async(server) as url:

        async def check(header):
            enabled = default if header is None else header.lower() == "true"
            headers = {} if header is None else {DOCUMENTATION_HEADER: header}
            async with Client(StreamableHttpTransport(url, headers=headers)) as client:
                result = await client.initialize()
                expected = "Custom server instructions.\n"
                if enabled:
                    expected = (
                        "Custom server instructions.\n\nCustom documentation hint.\n"
                    )
                assert result.instructions == expected
                for _ in range(2):
                    resources = await client.list_resources()
                    assert [str(r.uri) for r in resources] == ["test://unrelated"]
                    assert (await client.read_resource("test://unrelated"))[
                        0
                    ].text == "unchanged"

        await asyncio.gather(
            *(check(value) for value in [None, "true", "false", "TRUE"])
        )
        async with Client(
            StreamableHttpTransport(url, headers={DOCUMENTATION_HEADER: "invalid"}),
            auto_initialize=False,
        ) as client:
            with pytest.raises(McpError, match="must be true or false") as error:
                await client.initialize()
            assert error.value.error.code == -32602
    assert server.instructions == original


@pytest.mark.asyncio
@pytest.mark.parametrize("default", [None, "false", "true"])
async def test_documentation_without_http_header(
    default, documentation_app, monkeypatch
):
    """Without HTTP headers, the environment controls the instructions as for stdio."""
    if default is not None:
        monkeypatch.setenv("DC_ENABLE_DOCUMENTATION", default)
    app = documentation_app()
    async with Client(app.mcp) as client:
        result = await client.initialize()
    expected = "Custom server instructions.\n"
    if default == "true":
        expected = "Custom server instructions.\n\nCustom documentation hint.\n"
    assert result.instructions == expected


@pytest.mark.parametrize(("value", "expected"), [(" TRUE ", True), (" false ", False)])
def test_documentation_header_whitespace(value, expected, monkeypatch):
    monkeypatch.setattr(
        "datacommons_mcp.middleware.get_http_headers",
        lambda: {DOCUMENTATION_HEADER.lower(): value},
    )
    middleware = DocumentationMiddleware(
        enabled=False,
        base_instructions="base",
        documentation_instructions="base with documentation",
    )
    assert middleware._enabled() is expected
