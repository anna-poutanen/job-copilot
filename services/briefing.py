"""Turn today's agenda + inbox into a short, human morning brief."""
import config
from services import llm


def morning_brief(agenda: dict, inbox: dict) -> str:
    lines = []
    if agenda.get("events"):
        lines.append("TODAY'S EVENTS:")
        for e in agenda["events"]:
            lines.append(f"- {e['time_label']} — {e['title']}"
                         + (f" @ {e['location']}" if e['location'] else "")
                         + f" [{e['calendar']}]")
    else:
        lines.append("TODAY'S EVENTS: none on the calendar.")

    if inbox.get("configured"):
        lines.append("\nRECENT EMAIL (subjects):")
        for acct in inbox.get("accounts", []):
            for m in acct["messages"][:8]:
                lines.append(f"- [{acct['account']}] {m['from']}: {m['subject']}")

    context = "\n".join(lines)
    system = (
        "You are a concise personal chief-of-staff for a busy university student "
        "(varsity athlete + engineering design teams + jobs). Write a short, warm "
        "morning brief: 4-6 sentences. Lead with the day's shape and the one or two "
        "things that actually matter, then flag anything time-sensitive in the email. "
        "No emojis, no filler, no headers — just a quick human read-out."
    )
    prompt = f"Here is my raw data for today. Write my morning brief.\n\n{context}"
    return llm.generate(system, prompt, max_tokens=500, temperature=0.5)
