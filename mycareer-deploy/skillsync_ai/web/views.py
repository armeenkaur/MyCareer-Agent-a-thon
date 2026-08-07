from __future__ import annotations

from html import escape
from typing import Any


def backend_status(data: Any, backend: Any) -> str:
    phases = "".join(
        f"<tr><td>{escape(row['phase'].upper())}</td><td>{escape(row['status'])}</td>"
        f"<td>{row['progress']['completed']} / {row['progress']['total']}</td></tr>"
        for row in backend.phases()
    )
    return f"""
    <section class="grid">
      <div class="span-12">
        <span class="eyebrow">Backend handoff</span>
        <h1>MyCareer Compass backend is ready</h1>
        <p>Persistent SQLite domain layer and JSON API are active. Stitch frontend can connect to <code>/api/*</code>.</p>
      </div>
      <div class="span-4 card"><h2>Employees</h2><div class="metric-value">{len(data.employees)}</div></div>
      <div class="span-4 card"><h2>Competencies</h2><div class="metric-value">{len(data.competencies)}</div></div>
      <div class="span-4 card"><h2>Course catalogue</h2><div class="metric-value">{len(data.courses):,}</div></div>
      <div class="span-7 card"><h2>Phase state</h2><table><tr><th>Phase</th><th>Status</th><th>Progress</th></tr>{phases}</table></div>
      <div class="span-5 card"><h2>API entry points</h2>
        <p><code>GET /api/health</code></p><p><code>GET /api/meta</code></p>
        <p><code>POST /api/auth/login</code></p><p><code>GET /api/phases</code></p>
      </div>
    </section>
    """
