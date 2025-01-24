import subprocess
from pathlib import Path
import yaml

def gen_pdf(output_path):
    """Generate PDF from LaTeX."""
    subprocess.run(['pdflatex', output_path.with_suffix(".tex")], check=True, cwd=output_path.parent)
    # Delete temporary files
    output_path.with_suffix(".aux").unlink()
    output_path.with_suffix(".log").unlink()


output_file = "final_table.tex"

from jinja2 import Template

# Environments data
environments = {
    "Window": ["Window 2", "Window 3", "Window 4", "Window 5", "Window 6"],
    "Forest": ["Forest 2", "Forest 3", "Forest 4", "Forest 5", "Forest 6"],
    "Wall": ["Wall 2", "Wall 3", "Wall 4", "Wall 5", "Wall 6"],
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
\label{table1}
\caption{Performance Metrics for Different Methods Across Environments, Robot Types, and Methods.}
\centering
\footnotesize
\begin{tabular}{|c|c|c|c|c|c|c|c|c|c|c|c|c|}
\hline
\multirow{3}{*}{\textbf{Environment}} 
& \multicolumn{4}{c|}{\textbf{Success [\%]}} 
& \multicolumn{4}{c|}{\textbf{Cost}} 
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
{% for metric in ['success', 'cost', 'time'] %}
{% for robot in robot_types %}
{% for method in methods %}
& {% if robot in data.get(env, {}).get(method, {}) and metric in data[env][method][robot] %}
\scriptsize
{% if metric == 'success' %}
{% set ours = data[env]["Ours"][robot][metric] %}
{% set bl = data[env]["BL"][robot][metric] %}
{% if ours is not none and bl is not none %}
    {% if method == 'Ours' and ours > bl %}
    \textbf{{ "{{" ~ ours ~ "}}" }}
    {% elif method == 'BL' and bl > ours %}
    \textbf{{ "{{" ~ bl ~ "}}" }}
    {% else %}
    {{ data[env][method][robot][metric] }}
    {% endif %}
{% elif ours is not none %}
    {% if method == 'Ours' %}
    \textbf{{ "{{" ~ ours ~ "}}" }}
    {% else %}
    -
    {% endif %}
{% elif bl is not none %}
    {% if method == 'BL' %}
    \textbf{{ "{{" ~ bl ~ "}}" }}
    {% else %}
    -
    {% endif %}
{% else %}
-
{% endif %}
{% else %}
{% set ours = data[env]["Ours"][robot][metric][0] if data[env]["Ours"][robot][metric] is not none else None %}
{% set bl = data[env]["BL"][robot][metric][0] if data[env]["BL"][robot][metric] is not none else None %}
{% if ours is not none and bl is not none %}
    {% if method == 'Ours' and ours < bl %}
    {\textbf{{ "{{" ~ "%.1f" | format(ours) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "{%.1f}" | format(data[env]["Ours"][robot][metric][1]) }}}}
    {% elif method == 'BL' and bl < ours %}
    {\textbf{{ "{{" ~ "%.1f" | format(bl) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "{%.1f}" | format(data[env]["BL"][robot][metric][1]) }}}}
    {% else %}
    {{ "%.1f" | format(data[env][method][robot][metric][0]) }} {\tiny \textcolor{gray}{{ "{%.1f}" | format(data[env][method][robot][metric][1]) }}}
    {% endif %}
{% elif ours is not none %}
    {% if method == 'Ours' %}
    {\textbf{{ "{{" ~ "%.1f" | format(ours) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "{%.1f}" | format(data[env]["Ours"][robot][metric][1]) }}}}
    {% else %}
    -
    {% endif %}
{% elif bl is not none %}
    {% if method == 'BL' %}
    {\textbf{{ "{{" ~ "%.1f" | format(bl) ~ "}}" }}\hspace{0.5em}{\tiny \textcolor{gray}{{ "{%.1f}" | format(data[env]["BL"][robot][metric][1]) }}}}
    {% else %}
    -
    {% endif %}
{% else %}
-
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


    with open("../final_data.yaml", 'r') as f:
        data = yaml.safe_load(f)

    create_table(data, output_file)

    gen_pdf(Path(output_file))
