import subprocess
from pathlib import Path


def gen_pdf(output_path):
    """Generate PDF from LaTeX."""
    subprocess.run(['pdflatex', output_path.with_suffix(".tex")], check=True, cwd=output_path.parent)
    # Delete temporary files
    output_path.with_suffix(".aux").unlink()
    output_path.with_suffix(".log").unlink()


output_file = "final_table.tex"

from jinja2 import Template

# Environments data (reordered: Window, Wall, Forest)
environments = {
    "Window": ["Window 2", "Window 3"],
    "Forest": ["lego 2", "lego 3"],
}

# Methods and robot types
methods = ["Ours", "BL"]  # Ours and Baseline (BL)
robot_types = ["UR", "MP"]  # UR: Unicycles with Rods, MP: Multirotors with Cables

def create_table(data, output_file):
    """Generates a LaTeX table from the given data."""
    # LaTeX template
    template = Template(r"""
\documentclass[twocolumn]{article}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{multirow}

\begin{document}

% Compact table settings
\renewcommand{\arraystretch}{1.0} % Further tighten row height
\setlength{\tabcolsep}{5pt}       % Further tighten column padding

\begin{table*}[h!]
\caption{Performance Metrics for Different Methods Across Environments, Robot Types, and Methods.}
\centering
\footnotesize
\begin{tabular}{|c|c|c|c|c|c|c|c|c|c|c|c|c|}
\hline
\multirow{3}{*}{\textbf{Environment}} 
& \multicolumn{4}{c|}{\textbf{Success [\%]}} 
& \multicolumn{4}{c|}{\textbf{Error}} 
& \multicolumn{4}{c|}{\textbf{Time}} \\
\cline{2-13}
& \multicolumn{2}{c|}{\textbf{UR}} & \multicolumn{2}{c|}{\textbf{MP}} 
& \multicolumn{2}{c|}{\textbf{UR}} & \multicolumn{2}{c|}{\textbf{MP}} 
& \multicolumn{2}{c|}{\textbf{UR}} & \multicolumn{2}{c|}{\textbf{MP}} \\
\cline{2-13}
& \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} & \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} 
& \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} & \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} 
& \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} & \scriptsize \textbf{Ours} & \scriptsize \textbf{BL} \\
\hline
{% for group, envs in environments.items() %}
{% for env in envs %}
{{ env }}
{% for metric in ['success', 'error', 'time'] %}
{% for robot in robot_types %}
{% for method in methods %}
& {% if robot in data.get(env, {}).get(method, {}) and metric in data[env][method][robot] %}
\scriptsize
{% if metric == 'success' %}
{% set ours = data[env]["Ours"][robot][metric] %}
{% set bl = data[env]["BL"][robot][metric] %}
{% if method == 'Ours' and ours > bl %}
\textbf{{ "{{" ~ ours ~ "}}" }}
{% elif method == 'BL' and bl > ours %}
\textbf{{ "{{" ~ bl ~ "}}" }}
{% else %}
{{ data[env][method][robot][metric] }}
{% endif %}
{% else %}
{% set ours = data[env]["Ours"][robot][metric][0] %}
{% set bl = data[env]["BL"][robot][metric][0] %}
{% if method == 'Ours' and ours > bl %}
{\textbf{{ "{{" ~ "%.1f" | format(ours) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "%.1f" | format(data[env]["Ours"][robot][metric][1]) }}}}
{% elif method == 'BL' and bl > ours %}
{\textbf{{ "{{" ~ "%.1f" | format(bl) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "%.1f" | format(data[env]["BL"][robot][metric][1]) }}}}
{% else %}
{{ "%.1f" | format(data[env][method][robot][metric][0]) }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "%.1f" | format(data[env][method][robot][metric][1]) }}}
{% endif %}
{% endif %}
{% else %} - {% endif %}
{% endfor %}
{% endfor %}
{% endfor %}
\\
{% endfor %}
{% if not loop.last %}
\hline
{% endif %}
{% endfor %}
\hline
\end{tabular}
\end{table*}

\end{document}
""")
    # Render the LaTeX table
    latex_table = template.render(data=data, environments=environments, methods=methods, robot_types=robot_types).strip()

    # Save the LaTeX table to a file without extra lines
    with open(output_file, "w") as f:
        f.write("\n".join([line.strip() for line in latex_table.splitlines() if line.strip()]))

if __name__ == "__main__":
    # Full data for all environments, methods, and robot types
    data = {}
    for env_group, env_list in environments.items():
        for env in env_list:
            data[env] = {
                "Ours": {
                    "UR": {
                        "success": 100, "error": (15.0, 0.3), "time": (10.0, 0.2)
                    },
                    "MP": {
                        "success": 100, "error": (14.0, 0.4), "time": (9.5, 0.3)
                    },
                },
                "BL": {
                    "UR": {
                        "success": 99, "error": (16.0, 0.4), "time": (11.0, 0.3)
                    },
                    "MP": {
                        "success": 99, "error": (15.0, 0.5), "time": (10.0, 0.4)
                    },
                },
            }

    # Call the create_table function
    create_table(data, output_file)

    # Generate PDF
    gen_pdf(Path(output_file))
