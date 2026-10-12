import json

from app.agent.prompts import Passage, neutralise, wrap_passages
from app.agent.tools.base import AgentTool, ToolContext, ToolOutput, parse_args
from app.engineering.chat import remember_evidence, wrapped_packet
from app.engineering.retrieval import search_engineering
from app.engineering.schemas import SearchIn


def run(arguments: dict, ctx: ToolContext) -> str | ToolOutput:
    args, problem = parse_args(SearchIn, arguments)
    if args is None:
        return problem
    if not ctx.engineering_turn or not ctx.engineering_enabled:
        return "Engineering lookup is unavailable; capacity remains NOT VERIFIED."
    with ctx.deps.session() as session:
        result = search_engineering(session, args, remote=True)
        ids = []
        parts = []
        for packet in result["evidence"]:
            ids.append(packet["evidence_id"])
            remember_evidence(session, ctx.thread_id, packet, ctx.package_id)
            parts.append(wrapped_packet(packet))
        for metadata in result["metadata_only"]:
            parts.append(
                wrap_passages(
                    [
                        Passage(
                            content=json.dumps(metadata, ensure_ascii=False),
                            title=metadata["title"],
                            url=neutralise(
                                metadata.get("source_url")
                                or "metadata-only local source"
                            )
                            .replace('"', "'")
                            .replace("\n", " "),
                            scraped_at="unknown",
                        )
                    ]
                )
            )
        session.commit()
    return ToolOutput(
        text="\n\n".join(parts)
        or "No applicable eligible engineering evidence found; NOT VERIFIED.",
        update={
            "engineering_evidence_ids": ids,
            "engineering_metadata_ids": [
                item["version_id"] for item in result["metadata_only"]
            ],
        },
    )


search_engineering_knowledge = AgentTool(
    name="search_engineering_knowledge",
    description="Search engineering evidence with exact identity/applicability filters; results are not calculated safety ratings.",
    schema=SearchIn,
    run=run,
)
