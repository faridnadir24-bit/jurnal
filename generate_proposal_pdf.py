from fpdf import FPDF
import pymupdf


class AcademicProposalPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(left=18, top=16, right=18)
        self.set_auto_page_break(auto=False)

    def header(self):
        self.set_font("Helvetica", "B", 14.5)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6.5, "ACADEMIC RESEARCH PROPOSAL SUMMARY", align="C", new_x="LMARGIN", new_y="NEXT")
        
        self.set_font("Helvetica", "I", 9.5)
        self.set_text_color(0, 0, 0)
        self.cell(0, 5.5, "Application for Reddit Academic Data API Access (Non-Commercial Research)", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2.5)
        
        # Solid black divider rule
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4.5)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y() - 1, self.w - self.r_margin, self.get_y() - 1)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(0, 0, 0)
        self.cell(0, 5, "STT Wastukancana Purwakarta  |  Department of Informatics  |  Academic Research 2024  |  Page 1 of 1", align="C")


def build_pdf(output_path: str):
    pdf = AcademicProposalPDF()
    pdf.add_page()

    # Section 1: Title & Investigator Information
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5.5, "1. TITLE & INVESTIGATOR INFORMATION", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    box_x = pdf.get_x()
    box_y = pdf.get_y()
    box_w = pdf.w - pdf.l_margin - pdf.r_margin
    
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(0, 5, "Quantum-Like Modeling for Political Opinion Polarization with Memes as Cognitive Stimuli:", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "A Case Study of Indonesian Election Discourse", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    fields = [
        ("Principal Investigator", "Farid Nadir Amrulloh (Undergraduate Researcher, Informatics)"),
        ("Institutional Email", "251351034@wastukancana.ac.id"),
        ("Institution", "Sekolah Tinggi Teknologi (STT) Wastukancana Purwakarta, Indonesia"),
        ("Faculty Advisor", "Syariful Alam, M.Kom. (Department of Informatics, STT Wastukancana)"),
    ]

    for label, val in fields:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, 4.8, f"{label}:", align="L")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 4.8, val, new_x="LMARGIN", new_y="NEXT")

    box_h = pdf.get_y() - box_y + 2
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.35)
    pdf.rect(box_x, box_y - 1, box_w, box_h)
    
    pdf.ln(5.5)

    # Section 2: Background & Objectives
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5.5, "2. BACKGROUND & OBJECTIVES", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.2)
    bg_text = (
        "During the 2024 Indonesian Presidential Election, digital discourse exhibited severe affective polarization. "
        "Within neuropolitical theory, political memes operate as high-salience cognitive heuristics that rapidly prime ideological "
        "biases and reinforce in-group conformity. While classical Bayesian models struggle to account for cognitive interference, "
        "order effects, and context-dependent belief shifts, quantum-like cognitive modeling (utilizing Hilbert-space mathematical "
        "formalisms) provides a rigorous framework for human state superposition and decision uncertainty. This research analyzes "
        "how multimodal memes trigger state transitions leading to asymmetric opinion polarization across voter clusters."
    )
    pdf.multi_cell(0, 4.6, bg_text)
    pdf.ln(4.5)

    # Section 3: Data Requirements & Scope
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5.5, "3. DATA REQUIREMENTS & PLATFORM SCOPE", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.2)
    data_text = (
        "We request academic read-only API access via PRAW to extract historical submissions and discourse from two communities:\n"
        "- Target Subreddits: r/indonesia (broad civic and electoral discussions) and r/indonesiameme (satirical and multimodal memes).\n"
        "- Temporal Scope: October 1, 2023 - April 30, 2024 (encompassing candidate registration, official campaign periods, "
        "five televised presidential debates, election day on February 14, 2024, and Constitutional Court dispute rulings).\n"
        "- Ingestion Criteria: Public text submissions, comments, and direct image assets (.jpg, .png, .jpeg) matching election "
        "keywords: 'pemilu', 'pilpres', 'capres', 'anies', 'prabowo', 'ganjar'."
    )
    pdf.multi_cell(0, 4.6, data_text)
    pdf.ln(4.5)

    # Section 4: Methodology
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5.5, "4. METHODOLOGY & COMPUTATIONAL PIPELINE", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.2)
    method_text = (
        "- Extraction: Scripted collection with polite rate limiting (30 req/min with randomized jitter) adhering to robots.txt.\n"
        "- Preprocessing: Exclusion of automated bot accounts (e.g., AutoModerator), URL-only noise, and near-duplicate text.\n"
        "- Quantum-Like Modeling: Encoding extracted sentiment trajectories and visual meme features as complex state vectors "
        "in a multi-dimensional Hilbert space to quantify transition probabilities and cognitive interference across debate milestones."
    )
    pdf.multi_cell(0, 4.6, method_text)
    pdf.ln(4.5)

    # Section 5: Ethical Considerations & Data Privacy
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5.5, "5. ETHICAL CONSIDERATIONS & DATA PRIVACY COMPLIANCE", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9.2)
    ethics_text = (
        "- Strictly Academic & Non-Commercial: Exclusively conducted for an undergraduate thesis and open-science publication. "
        "The dataset will never be used for commercial profiling, targeted advertising, or training commercial AI/LLM models.\n"
        "- Cryptographic Anonymization: All usernames are pseudonymized at ingestion via salted SHA-256 hashing (anon_<hash[:16]>).\n"
        "- PII Elimination: Automated regular expressions strip direct identifiers (phone numbers, email addresses, and @mentions).\n"
        "- Storage & Compliance: Hosted on encrypted, password-protected academic drives strictly aligned with Reddit Developer Terms."
    )
    pdf.multi_cell(0, 4.6, ethics_text)

    pdf.output(output_path)
    print(f"Generated PDF at: {output_path}")


if __name__ == "__main__":
    out = "d:/CTF/Reddit_API_Research_Proposal_Farid_Nadir_Amrulloh.pdf"
    build_pdf(out)
    
    doc = pymupdf.open(out)
    print(f"Total Page Count: {doc.page_count}")
    if doc.page_count == 1:
        print("PERFECT: Exact 1 page confirmed.")
    else:
        print(f"WARNING: Page count is {doc.page_count}, needs adjustment!")
