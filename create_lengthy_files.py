"""Script to generate 12 new, lengthy, multi-format benchmark documents across 4 domains."""
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent
UNORGANISED_DIR = BASE_DIR / "Unorganised Folder"


def make_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]):
    """Create a valid .docx file with multiple lengthy sections and paragraphs."""
    root = ET.Element("w:document", {
        "xmlns:w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    })
    body = ET.SubElement(root, "w:body")

    # Title paragraph
    p_title = ET.SubElement(body, "w:p")
    pPr = ET.SubElement(p_title, "w:pPr")
    jc = ET.SubElement(pPr, "w:jc", {"w:val": "center"})
    r_title = ET.SubElement(p_title, "w:r")
    rPr = ET.SubElement(r_title, "w:rPr")
    ET.SubElement(rPr, "w:b")
    t_title = ET.SubElement(r_title, "w:t")
    t_title.text = title

    for sec_heading, paragraphs in sections:
        # Section Heading
        p_head = ET.SubElement(body, "w:p")
        pPr_h = ET.SubElement(p_head, "w:pPr")
        r_head = ET.SubElement(p_head, "w:r")
        rPr_h = ET.SubElement(r_head, "w:rPr")
        ET.SubElement(rPr_h, "w:b")
        t_head = ET.SubElement(r_head, "w:t")
        t_head.text = sec_heading

        # Paragraphs
        for para in paragraphs:
            p_para = ET.SubElement(body, "w:p")
            r_para = ET.SubElement(p_para, "w:r")
            t_para = ET.SubElement(r_para, "w:t")
            t_para.text = para

    doc_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    ct_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        '</Types>'
    ).encode("utf-8")

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
        '</Relationships>'
    ).encode("utf-8")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", doc_xml)


def make_pdf(path: Path, title: str, sections: list[tuple[str, list[str]]]):
    """Create a valid multi-page PDF 1.4 file formatted for extract_text_from_pdf."""
    # Split content across pages (~35 lines per page)
    pages_lines = []
    current_page = []

    def add_line(l):
        nonlocal current_page
        current_page.append(l)
        if len(current_page) >= 35:
            pages_lines.append(current_page)
            current_page = []

    add_line(title)
    add_line("=" * len(title))
    add_line("")

    for sec_heading, paragraphs in sections:
        add_line("")
        add_line(f"## {sec_heading}")
        add_line("-" * (len(sec_heading) + 3))
        add_line("")
        for para in paragraphs:
            # Wrap paragraph into ~75 character lines
            words = para.split()
            cur_line = []
            cur_len = 0
            for w in words:
                if cur_len + len(w) + 1 > 75:
                    add_line(" ".join(cur_line))
                    cur_line = [w]
                    cur_len = len(w)
                else:
                    cur_line.append(w)
                    cur_len += len(w) + 1
            if cur_line:
                add_line(" ".join(cur_line))
            add_line("")

    if current_page:
        pages_lines.append(current_page)

    num_pages = len(pages_lines)

    # Build PDF objects
    # 1: Catalog
    # 2: Pages
    # 3: Font
    # For each page i (0-based):
    #   Page obj: 4 + 2*i
    #   Stream obj: 5 + 2*i
    page_obj_ids = [4 + 2 * i for i in range(num_pages)]
    stream_obj_ids = [5 + 2 * i for i in range(num_pages)]

    objects = {}

    # Catalog
    objects[1] = "<< /Type /Catalog /Pages 2 0 R >>"

    # Pages
    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>"

    # Font
    objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for i in range(num_pages):
        pid = page_obj_ids[i]
        sid = stream_obj_ids[i]

        lines = pages_lines[i]
        stream_content_lines = ["BT", "/F1 10 Tf", "13 TL", "45 745 Td"]
        for line in lines:
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_content_lines.append(f"({safe_line}) '")
        stream_content_lines.append("ET")
        stream_data = "\n".join(stream_content_lines)

        objects[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {sid} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        objects[sid] = f"<< /Length {len(stream_data)} >>\nstream\n{stream_data}\nendstream"

    # Assemble PDF with cross-reference table
    output = bytearray()
    output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = {}
    for obj_id in sorted(objects.keys()):
        offsets[obj_id] = len(output)
        output.extend(f"{obj_id} 0 obj\n{objects[obj_id]}\nendobj\n".encode("latin-1"))

    xref_offset = len(output)
    total_objs = max(objects.keys()) + 1
    output.extend(f"xref\n0 {total_objs}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, total_objs):
        off = offsets[obj_id]
        output.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    output.extend(trailer.encode("latin-1"))

    path.write_bytes(output)


def make_txt(path: Path, title: str, sections: list[tuple[str, list[str]]]):
    """Create a structured lengthy text file."""
    lines = [
        title,
        "=" * len(title),
        "",
    ]
    for sec_heading, paragraphs in sections:
        lines.append(f"## {sec_heading}")
        lines.append("-" * (len(sec_heading) + 3))
        lines.append("")
        for p in paragraphs:
            lines.append(p)
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# =============================================================================
# DETAILED DOMAIN CONTENT GENERATORS
# =============================================================================

def get_education_content_1():
    title = "COMPREHENSIVE K-12 AND COLLEGIATE CURRICULAR FRAMEWORK 2026"
    sections = [
        (
            "1. Pedagogical Scaffolding and Instructional Design",
            [
                "This comprehensive curriculum guide articulates systemic pedagogical methodologies across modern K-12 and post-secondary educational ecosystems. Modern cognitive psychology emphasizes structured instructional scaffolding, allowing students to transition progressively from guided inquiry to autonomous mastery. Educators must integrate low-stakes formative checks into weekly syllabi to calibrate conceptual pacing.",
                "Diagnostic telemetry from blended classrooms indicates that students provided with multi-modal instructional resources achieve a 38% higher rate of concept retention. Scaffolding frameworks must address diverse student demographics, including English Language Learners (ELL) and neurodivergent cohorts requiring differentiated pacing and individualized pedagogical interventions.",
                "In order to sustain cognitive engagement, lesson plans should combine direct instruction segments limited to twelve minutes with structured peer-to-peer discourse and collaborative problem-solving labs. Classroom observations demonstrate that passive lecture formats exceeding fifteen minutes exhibit sharp declines in pupil attention span and formative assessment retention scores.",
            ]
        ),
        (
            "2. Formative Assessment Rubrics and Competency Standards",
            [
                "Assessment strategies should emphasize rubric-based competency evaluations rather than punitive summative grading schemes. Rubrics establish explicit criteria across cognitive domains: knowledge retrieval, analytical synthesis, argumentative coherence, and empirical application. By sharing transparent evaluation matrices prior to project initiation, instructors empower learners to self-regulate and monitor academic progression.",
                "Bi-weekly formative feedback loops provide educators with real-time empirical diagnostic insights into persistent learning obstacles. When teachers utilize rubric-aligned qualitative commentaries instead of numerical marks alone, pupils display a 45% increase in revised assignment submission rates and measurable improvements in core reading comprehension benchmarks.",
                "Standardized testing calibrations must account for socio-economic factors and linguistic nuances. Cross-departmental committees are mandated to perform annual reliability audits on institutional test items, eliminating culturally biased vocabulary and ensuring accessibility accommodations across state examination protocols.",
            ]
        ),
        (
            "3. Special Education Accommodation, IEP Compliance, and Inclusive Classrooms",
            [
                "Federal statutory compliance mandates that Individualized Education Programs (IEPs) and Section 504 plans remain fully operational across all instructional settings. Co-teaching models pairing certified general educators with special education specialists yield the highest rates of academic mastery among students with specific learning disabilities and attention deficit challenges.",
                "Universal Design for Learning (UDL) principles must be embedded into all digital learning management systems (LMS). Course syllabi, lecture transcripts, tactile manipulatives, and visual graphic organizers ensure equitable access across sensory modalities without requiring stigmatizing individual accommodations.",
                "Multidisciplinary review panels comprising psychologists, speech pathologists, classroom educators, and family liaisons must convene semi-annually to reassess student behavioral intervention plans (BIP) and adjust assistive technology allocations to sustain inclusive classroom participation.",
            ]
        ),
        (
            "4. Faculty Professional Development and Instructional Telemetry",
            [
                "Continuous professional learning communities (PLCs) form the backbone of sustainable institutional pedagogical advancement. School districts investing in peer observation cycles and video-recorded instructional debriefs observe significant reductions in first-year educator turnover and marked elevations in student standardized literacy outcomes.",
                "Instructional telemetry derived from classroom observations underscores the importance of teacher-student dialogic ratios. Classrooms where instructors facilitate student-led inquiry dialogues produce markedly deeper conceptual understanding in STEM subjects than environments relying predominantly on rote memorization drills.",
            ]
        ),
        (
            "5. Quantitative Case Studies and Empirical Longitudinal Outcomes",
            [
                "In a three-year controlled trial encompassing 4,200 Grade 7 through 10 students across eight municipal districts, classrooms utilizing the structured scaffolding framework demonstrated a statistically significant 1.2 standard deviation increase on the National Assessment of Educational Progress (NAEP) mathematics and reading composites.",
                "Subgroup analysis revealed that underperforming cohorts closed historical achievement gaps by 41% within twenty-four months of continuous intervention. Qualitative survey responses indicated that student perceived self-efficacy and classroom belonging metrics rose to 87% satisfaction ratings.",
                "District budgetary allocations were recalibrated to establish dedicated instructional coaching funds, ensuring that every novice teacher receives at least sixty hours of one-on-one pedagogical mentoring during their induction academic year.",
            ]
        ),
        (
            "6. Implementation Timelines and Curricular Milestones",
            [
                "Phase I (Months 1-6): Comprehensive audit of existing school district syllabi and learning outcome alignment with state standards. Conduct baseline diagnostic standardized assessments across all participating cohorts.",
                "Phase II (Months 7-18): District-wide rollout of UDL digital lesson templates, co-teaching professional development workshops, and bi-weekly PLC collaborative planning periods.",
                "Phase III (Months 19-36): Longitudinal evaluation of formative assessment rubric consistency, external peer review panel audits, and publication of the multi-district educational equity index.",
            ]
        ),
    ]
    return title, sections


def get_education_content_2():
    title = "ACADEMIC SYMPOSIUM PROCEEDINGS ON HIGHER EDUCATION TEACHING INNOVATION"
    sections = [
        (
            "1. University Pedagogy and Hybrid Classroom Engagement",
            [
                "The annual symposium on collegiate instruction convenes university faculty, academic deans, and educational researchers to investigate emerging delivery paradigms across tertiary education. As institutions transition between asynchronous online modules and active seminar sessions, the demand for rigorous pedagogical frameworks has intensified.",
                "Empirical research presented across thirty university departments confirms that active learning strategies, including inverted or flipped classroom models, double conceptual mastery rates in introductory undergraduate STEM courses compared to traditional lecture formats. Students review foundational theoretical material independently prior to participating in faculty-guided analytical workshops.",
                "Engagement analytics collected from over 15,000 university course portals demonstrate that interactive polling, immediate formative comprehension checks, and collaborative problem-solving breakout sessions directly counteract asynchronous student attrition rates.",
            ]
        ),
        (
            "2. Curriculum Modernization, Syllabus Alignment, and Learning Outcomes",
            [
                "Academic governance committees must oversee rigorous curriculum modernization cycles to guarantee that collegiate degree programs align with contemporary multidisciplinary demands. Every syllabus must articulate measurable, student-centered learning outcomes linked to professional accreditation and academic research competencies.",
                "Course design rubrics developed by the faculty senate emphasize constructive alignment, wherein assessment tasks directly mirror instructional activities and core cognitive objectives. The integration of capstone research seminars and experiential practicums fosters critical inquiry and prepares graduates for advanced scholarly investigation.",
                "Institutions must conduct longitudinal tracking of student learning outcome attainment across foundational general education requirements, identifying curricular bottlenecks in quantitative reasoning and argumentative prose composition.",
            ]
        ),
        (
            "3. Student Retention Analytics, Mentorship Circles, and Academic Advising",
            [
                "Retention predictive modeling indicates that early academic warning flags during the initial six weeks of the freshman semester correlate with first-year dropout probabilities exceeding 60%. Implementing proactive advising check-ins and faculty mentorship circles increases degree completion rates by 22% among vulnerable student cohorts.",
                "Tutoring centers staffed by trained undergraduate peer mentors provide accessible academic remediation in high-attrition foundational calculus, chemistry, and organic biology sequences. Peer-assisted study sessions (PASS) reduce course failure rates by over a full letter grade.",
                "Holistic student support structures combining academic coaching, mental health counseling services, and supplemental financial micro-grants constitute essential institutional safeguards against undergraduate departure.",
            ]
        ),
        (
            "4. Institutional Accreditation, Pedagogical Scholarship, and Educational Equity",
            [
                "Regional higher education accrediting bodies increasingly evaluate universities based on empirical evidence of equitable teaching outcomes across historically underrepresented student populations. Departments must demonstrate disaggregated student progression metrics and continuous curricular self-study protocols.",
                "Scholarship of Teaching and Learning (SoTL) grants incentivize tenure-track faculty to conduct peer-reviewed experimental studies on instructional methodologies, establishing teaching excellence as a primary metric in academic promotion and tenure determinations.",
            ]
        )
    ]
    return title, sections


def get_education_content_3():
    title = "LONGITUDINAL PEDAGOGICAL ASSESSMENT AND DISTRICT COGNITIVE REVIEW"
    sections = [
        (
            "1. District-Wide Literacy Benchmarks and Instructional Scaffolding",
            [
                "This longitudinal research report analyzes standardized reading comprehension and computational mathematics performance metrics across twenty-four metropolitan public school districts. Over a three-year observation window, instructional coaches evaluated the impact of structured phonetic literacy curricula and tiered reading interventions.",
                "Early childhood reading diagnostics indicate that systematic explicit instruction in phonemic awareness, vocabulary acquisition, and reading fluency yields a 74% proficiency rate by Grade 3, compared to 48% in districts utilizing unguided balanced literacy methodologies.",
                "Elementary reading specialists emphasize guided reading groups with decodable texts aligned to developmental reading stages. Teachers incorporate graphic organizers and sentence stems to scaffold analytical writing exercises across elementary social studies and science modules.",
            ]
        ),
        (
            "2. STEM Instructional Efficacy, Inquiry-Based Labs, and Mathematics Pedagogy",
            [
                "Secondary mathematics outcomes demonstrate that conceptual understanding must precede algorithmic computation drills. Middle school algebra curricula incorporating visual modeling, number lines, and concrete manipulatives cultivate deeper mathematical intuition and reduce student math anxiety.",
                "Inquiry-based laboratory science programs encourage middle and high school learners to formulate experimental hypotheses, gather empirical data, and compose evidence-based argumentative lab reports using the Claim-Evidence-Reasoning (CER) pedagogical framework.",
                "Professional development workshops focused on mathematical discourse encourage educators to elicit multiple student problem-solving strategies, fostering metacognitive awareness and mathematical flexibility in secondary classrooms.",
            ]
        ),
        (
            "3. Continuous Educator Evaluation, Classroom Telemetry, and Rubric Calibration",
            [
                "Teacher evaluation frameworks must transition away from high-stakes annual walkthroughs toward continuous supportive instructional coaching. Coaches conduct bi-weekly fifteen-minute observations followed by collaborative reflective debriefs focused on specific instructional growth targets.",
                "Classroom observational metrics track student questioning depth, teacher talk time versus student discourse, and the frequency of high-order cognitive prompts based on Bloom's Revised Taxonomy. Districts employing supportive coaching models report significant gains in teacher retention and instructional consistency.",
                "Standardized rubric calibrations conducted during district-wide professional development days ensure grading reliability across secondary English Language Arts and Social Studies essay examinations.",
            ]
        ),
        (
            "4. School Climate, Community Engagement, and Socio-Emotional Learning Integration",
            [
                "A positive school climate directly correlates with reduced disciplinary infractions and elevated standardized academic attainment. Integrating evidence-based socio-emotional learning (SEL) programs fosters self-regulation, empathy, and constructive conflict resolution skills among students.",
                "Parent-school liaison initiatives, including bilingual family literacy nights and transparent online grade reporting portals, enhance guardian involvement and strengthen community-school partnerships across urban educational districts.",
            ]
        )
    ]
    return title, sections


def get_finance_content_1():
    title = "ANNUAL TREASURY AUDIT, CASH FLOW ANALYSIS, AND CAPITAL ALLOCATION REVIEW"
    sections = [
        (
            "1. Corporate Cash Flow Management and Working Capital Optimization",
            [
                "This comprehensive treasury memorandum analyzes group-wide cash flow generation, working capital metrics, and liquidity positioning across multinational operational subsidiaries. Maintaining disciplined working capital cycles is paramount amidst fluctuating benchmark borrowing rates and macroeconomic supply chain volatility.",
                "Days Sales Outstanding (DSO) contracted from 54.2 days to 46.8 days following the implementation of automated accounts receivable matching and early-settlement incentive discount programs. Days Payable Outstanding (DPO) was tactically extended to 62.5 days without triggering supplier credit downgrades or relationship friction.",
                "Consolidated free cash flow (FCF) reached $142.6 million for the trailing twelve months, representing a 118% conversion rate of adjusted net earnings. Operating cash flows provided robust coverage for recurring maintenance capital expenditures and ongoing research investments.",
            ]
        ),
        (
            "2. Capital Structure, Debt Maturity Profiles, and Interest Rate Hedging",
            [
                "The corporate capital structure consists of $850 million in senior unsecured revolving credit facilities, $600 million in 4.75% senior notes maturing in 2031, and $250 million in asset-backed commercial paper facilities. Net debt to trailing EBITDA stands conservatively at 1.85x, well within bank covenant thresholds of 3.50x.",
                "To mitigate exposure to variable SOFR benchmark rate volatility, the treasury department maintains $450 million in amortizing interest rate swap agreements, fixing effective borrowing costs at 3.82% through fiscal year 2028. Sensitivity stress testing indicates that a 100 bps parallel upward rate shift impacts net interest expenses by less than $2.4 million annually.",
                "The group maintains liquidity buffers of $215 million in unencumbered cash equivalents and $400 million in undrawn committed revolving credit capacity, ensuring over 180 days of operational runway without reliance on external capital markets.",
            ]
        ),
        (
            "3. EBITDA Reconciliation, Margin Bridge, and Segmental Profitability",
            [
                "Adjusted EBITDA expanded by 240 basis points year-over-year to 22.4%, driven by operational leverage, supply chain rationalization, and premium tier product pricing resilience. Gross profit margins expanded to 44.8% despite inflationary pressures in raw material logistics and industrial energy tariffs.",
                "Non-recurring restructuring expenses, equity-based compensation charges, and foreign exchange remeasurement adjustments are itemized within the GAAP-to-non-GAAP reconciliation tables, providing credit rating agencies and equity analysts with transparent underlying operating metrics.",
                "Segmental EBITDA breakdowns highlight that enterprise cloud solutions generated $98.4 million at a 31.2% operating margin, while consumer retail operations contributed $44.2 million at a 14.1% operating margin.",
            ]
        ),
        (
            "4. Capital Allocation Framework, Share Repurchases, and Dividend Policy",
            [
                "The board-approved capital allocation hierarchy prioritizes: (1) organic high-return ROIC project funding, (2) accretive strategic tuck-in acquisitions, (3) regular progressive dividend distributions, and (4) opportunistic share repurchases executed below intrinsic equity valuations.",
                "The quarterly dividend payout was increased by 6.5% to $0.32 per common share, representing a sustainable 28% payout ratio against free cash flow. Cumulative share repurchases under the current $200 million authorization totaled $65 million across the prior three fiscal quarters.",
            ]
        )
    ]
    return title, sections


def get_finance_content_2():
    title = "CONSOLIDATED FINANCIAL STATEMENT AND BALANCE SHEET AUDIT REPORT"
    sections = [
        (
            "1. Consolidated Balance Sheet Reconciliation and Asset Valuations",
            [
                "Independent certified public accountants completed the annual consolidated audit of the financial statements, comprising the consolidated balance sheet, statement of comprehensive income, statement of stockholders equity, and cash flows in conformity with US GAAP and IFRS standards.",
                "Total consolidated assets increased to $3.84 billion, supported by prudent capital investments in core manufacturing capacity and accretive intellectual property acquisitions. Goodwill and identifiable intangible assets were subjected to annual impairment testing under ASC 350, with no impairment triggers identified.",
                "Allowance for credit losses on trade receivables was calibrated under the Current Expected Credit Losses (CECL) methodology, maintaining a conservative reserve ratio of 2.15% against gross receivables based on historical recovery curves and forward macroeconomic scenarios.",
            ]
        ),
        (
            "2. Capital Expenditure Depreciation, Lease Accounting, and Liabilities",
            [
                "Property, plant, and equipment depreciation schedules reflect straight-line amortization over estimated useful economic lifespans ranging from 5 to 30 years. Additions to capital assets totaled $118.5 million, focused on facility automation, green energy infrastructure, and enterprise data center upgrades.",
                "Operating lease right-of-use (ROU) assets and corresponding current and long-term lease liabilities under ASC 842 total $184.2 million and $198.6 million respectively. Weighted-average discount rates applied to lease payment obligations averaged 4.65% with remaining lease tenures of 7.2 years.",
                "Long-term liabilities encompass $1.2 billion in senior term debt, $145 million in deferred tax liabilities, and $38 million in actuarial pension obligations. Pension funding ratios across defined benefit plans stand at 94.2% based on conservative actuarial discount rate assumptions.",
            ]
        ),
        (
            "3. Revenue Recognition Principles, Deferred Income, and Contract Assets",
            [
                "Revenue recognition adheres strictly to ASC 606 five-step model guidelines. Multi-element software contracts and long-term service agreements are disaggregated into distinct performance obligations, allocating transaction consideration based on stand-alone selling prices (SSP).",
                "Deferred revenue liabilities representing unearned subscription billings expanded to $286.4 million, providing high forward revenue visibility with 78% expected to be recognized as operational revenue within the succeeding twelve-month fiscal period.",
                "Contract acquisition costs, including sales commissions paid upon contract execution, are capitalized and amortized systematically over the estimated average customer relationship duration of 60 months.",
            ]
        ),
        (
            "4. Internal Controls, Sarbanes-Oxley 404 Compliance, and Audit Findings",
            [
                "Management evaluated the effectiveness of internal controls over financial reporting (ICFR) based on the COSO Integrated Framework. The independent auditor issued an unqualified clean audit opinion, confirming the absence of material weaknesses or significant deficiencies in financial reporting controls.",
                "Information technology general controls (ITGC) governing financial ledger databases, privileged user access management, and automated journal entry authorization matrices were verified to operate effectively throughout the audit observation period.",
            ]
        )
    ]
    return title, sections


def get_finance_content_3():
    title = "PORTFOLIO RISK DISCLOSURE AND ASSET ALLOCATION ASSESSMENT"
    sections = [
        (
            "1. Macroeconomic Risk Modeling and Multi-Asset Class Exposure",
            [
                "This comprehensive institutional risk disclosure articulates the macroeconomic exposure profile, factor sensitivity, and Value-at-Risk (VaR) parameters across our $12.5 billion multi-asset investment portfolio. Global financial markets face cross-currents driven by monetary tightening cycles, yield curve inversions, and geopolitical shifts.",
                "Portfolio allocation spans 45% global developed equities, 30% investment-grade fixed income, 15% private market alternative assets (real estate and private credit), and 10% cash equivalents and tactical sovereign debt instruments. Asset weighting guidelines enforce strict concentration limits, capping individual issuer exposure at 2.5% of total fund equity.",
                "Parametric 99% 10-day Value-at-Risk is modeled at $185 million, representing 1.48% of net asset value (NAV). Historical scenario backtesting against the 2008 Lehman crisis and 2020 pandemic dislocation indicates adequate portfolio resilience under 3-standard-deviation tail-risk events.",
            ]
        ),
        (
            "2. Credit Default Swaps, Derivative Overlays, and Counterparty Risk",
            [
                "Defensive derivative overlays are deployed to hedge equity downside beta and credit spread blowout risks. The portfolio holds $800 million notional in credit default swap (CDS) index protection on North American and European high-yield credit baskets.",
                "All bilateral over-the-counter (OTC) derivative agreements operate under standard ISDA Master Agreements accompanied by daily Credit Support Annex (CSA) two-way collateralization. Margin thresholds are zero with eligible collateral restricted to US Treasury bills and cash.",
                "Prime brokerage counterparty exposure is diversified across five Tier-1 global institutions, with daily automated collateral sweeps preventing uncollateralized settlement balances from exceeding $15 million with any single intermediary.",
            ]
        ),
        (
            "3. Fixed Income Duration Profiling, Convexity, and Credit Spread Dynamics",
            [
                "The fixed income sleeve maintains an effective modified duration of 4.35 years, positioned defensively against intermediate yield curve shifts. Portfolio convexity is positive at 0.38, providing asymmetric return characteristics during severe interest rate rally scenarios.",
                "Credit quality metrics remain robust, with 88% of fixed income holdings carrying BBB+ or higher investment-grade ratings from S&P and Moody's. High-yield exposures are concentrated in senior secured asset-backed tranches with substantial tangible collateral coverage ratios exceeding 2.2x loan-to-value.",
                "Emerging market local currency debt exposure is capped at 3% of aggregate fund capital, strictly hedged against currency depreciation via rolling foreign exchange forward contracts.",
            ]
        ),
        (
            "4. Regulatory Capital Adequacy, Solvency II Compliance, and Stress Testing",
            [
                "Statutory capital ratios satisfy all Tier-1 capital adequacy standards and Solvency II solvency capital requirement (SCR) coverage thresholds, maintaining a comfortable 220% surplus over statutory minimums.",
                "Semi-annual stress testing exercises conducted in coordination with central bank supervisory authorities model hypothetical stagflation shocks characterized by simultaneous 250 bps rate hikes, 25% equity declines, and 300 bps corporate spread widening, verifying fund solvency and liquidity continuity.",
            ]
        )
    ]
    return title, sections


def get_law_content_1():
    title = "APPELLATE LITIGATION BRIEF: STATUTORY INTERPRETATION AND ANTITRUST LIABILITY"
    sections = [
        (
            "1. Procedural History, Interlocutory Appellate Review, and Jurisdiction",
            [
                "This appellate brief is submitted on behalf of appellant in the United States Court of Appeals, challenging the district court's interlocutory order denying summary judgment and granting preliminary injunctive relief under 28 U.S.C. Section 1292(b). The legal issue presented turns on the statutory scope of Section 2 of the Sherman Antitrust Act.",
                "Appellate jurisdiction is properly invoked pursuant to a timely certified order of the district court finding substantial ground for difference of opinion on a controlling question of law. The standard of review applied by this court is de novo for all issues of statutory interpretation and statutory standing.",
                "The district court erred in holding that plaintiff possessed antitrust standing to assert claims based on speculative future market foreclosure without establishing direct antitrust injury under the Clayton Act Section 4 standards established in Brunswick Corp. v. Pueblo Bowl-O-Mat, Inc.",
            ]
        ),
        (
            "2. Substantive Sherman Act Doctrine and Relevant Product Market Definition",
            [
                "Under established Supreme Court antitrust jurisprudence (Ohio v. American Express Co. and Spectrum Sports, Inc. v. McQuillan), a plaintiff asserting monopolization or attempted monopolization must prove: (1) possession of monopoly power in a properly defined relevant antitrust market, and (2) willful acquisition or maintenance of that power through anti-competitive exclusionary conduct.",
                "Plaintiff failed as a matter of law to present admissible econometric cross-elasticity of demand evidence to support its gerrymandered relevant market definition. When properly accounting for substitute products, defendant's market share does not exceed 26%, far below the presumptive 65% threshold required to establish monopoly power.",
                "Furthermore, unilateral refusal to license proprietary technology to commercial rivals cannot constitute an antitrust violation absent the narrow, disfavored Aspen Skiing exception, which does not apply where defendant never engaged in a prior voluntary course of dealing with plaintiff.",
            ]
        ),
        (
            "3. Contractual Arbitration Clause Enforcement and Federal Arbitration Act Preemption",
            [
                "In the alternative, the underlying commercial agreement between the parties contains an enforceable, mandatory arbitration clause requiring all disputes, including statutory antitrust claims, to be resolved via binding arbitration administered by the American Arbitration Association (AAA).",
                "Under Section 2 of the Federal Arbitration Act (FAA) and Supreme Court precedent in Henry Schein, Inc. v. Archer & White Sales, Inc., where parties incorporate commercial arbitration rules delegating questions of arbitrability to the arbitrator, courts are without jurisdiction to rule on the threshold scope of arbitrability.",
                "The district court committed reversible legal error by refusing to compel arbitration and stay judicial proceedings pursuant to 9 U.S.C. Section 3, disregarding federal policy favoring arbitration agreements according to their explicit contractual terms.",
            ]
        ),
        (
            "4. Conclusion and Relief Requested",
            [
                "For the foregoing reasons, Appellant respectfully requests that this Court reverse the order of the district court, vacate the preliminary injunction, and remand with instructions to enter summary judgment in favor of Appellant or, in the alternative, compel binding arbitration under the FAA.",
            ]
        )
    ]
    return title, sections


def get_law_content_2():
    title = "MASTER SERVICES AGREEMENT: COMMERCIAL TERMS, INDEMNIFICATION, AND GOVERNING LAW"
    sections = [
        (
            "1. Engagement Scope, Statement of Work, and Service Level Warranties",
            [
                "This Master Services Agreement ('Agreement') is entered into as of the Effective Date by and between Enterprise Client Inc., a Delaware corporation, and Global Technology Solutions LLC, a New York limited liability company. Each party shall be individually referred to as a 'Party' and collectively as the 'Parties'.",
                "Provider warrants that all professional services and software deliverables furnished under any Statement of Work (SOW) shall be performed in a professional, workmanlike manner conforming to prevailing industry standards and the explicit functional specifications set forth in Exhibit A.",
                "In the event of any service level agreement (SLA) downtime or material breach of performance warranties, Provider shall promptly rectify the non-conformity within ten (10) business days of written notice, or Client shall be entitled to liquidated SLA service credits as specified in the applicable SOW.",
            ]
        ),
        (
            "2. Mutual Indemnification, Intellectual Property Protection, and Infringement Defense",
            [
                "Provider shall defend, indemnify, and hold harmless Client, its affiliates, directors, officers, and employees against any third-party claims, lawsuits, or regulatory enforcement proceedings alleging that the deliverables, software, or documentation infringe upon any valid patent, copyright, trademark, or trade secret.",
                "Client shall defend and indemnify Provider against any claims arising out of Client's unauthorized modification of the deliverables or Client's provision of infringing proprietary data to Provider in violation of third-party intellectual property licenses or statutory data privacy regulations.",
                "The indemnified Party must provide prompt written notification of any indemnifiable claim, grant the indemnifying Party sole control over litigation defense and settlement negotiations, and cooperate reasonably in the defense at the indemnifying Party's expense.",
            ]
        ),
        (
            "3. Limitation of Liability, Exclusion of Consequential Damages, and Liability Caps",
            [
                "TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE STATUTORY LAW, NEITHER PARTY SHALL BE LIABLE TO THE OTHER FOR ANY INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, PUNITIVE, OR EXEMPLARY DAMAGES, INCLUDING LOSS OF PROFITS, REVENUE, DATA, OR BUSINESS INTERRUPTION, ARISING OUT OF OR IN CONNECTION WITH THIS AGREEMENT.",
                "EXCEPT FOR GROSS NEGLIGENCE, WILLFUL MISCONDUCT, BREACH OF CONFIDENTIALITY OBLIGATIONS UNDER SECTION 8, OR INDEMNIFICATION OBLIGATIONS UNDER SECTION 6, EACH PARTY'S TOTAL AGGREGATE LIABILITY UNDER THIS AGREEMENT SHALL BE STRICTLY LIMITED TO THE TOTAL FEES PAID OR PAYABLE BY CLIENT UNDER THE APPLICABLE STATEMENT OF WORK IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.",
                "The Parties acknowledge that the contractual liability caps and damage disclaimers reflect a bargained-for allocation of commercial risk and constitute an essential basis of the bargain between the Parties.",
            ]
        ),
        (
            "4. Governing Law, Dispute Resolution, and Arbitration Venue",
            [
                "This Agreement shall be governed by, construed, and enforced in accordance with the substantive laws of the State of New York, without regard to its conflict of law principles or the UN Convention on Contracts for the International Sale of Goods.",
                "Any dispute arising out of or relating to this Agreement shall be resolved by confidential, binding arbitration administered by JAMS in New York, New York, before a single retired judge arbitrator in accordance with JAMS Comprehensive Arbitration Rules.",
            ]
        )
    ]
    return title, sections


def get_law_content_3():
    title = "CROSS-BORDER STATUTORY COMPLIANCE FILING AND ARBITRATION SUBMISSION"
    sections = [
        (
            "1. Statutory Regulatory Compliance, Sanctions Screening, and Export Controls",
            [
                "This regulatory compliance disclosure filing details corporate adherence to multinational statutory mandates, including the Foreign Corrupt Practices Act (FCPA), the UK Bribery Act 2010, the European General Data Protection Regulation (GDPR), and US Treasury OFAC sanctions frameworks.",
                "The compliance audit committee instituted continuous real-time customer due diligence (CDD) and sanctions screening across all international cross-border payment gateways. Over 2.4 million transactions were screened against OFAC Specially Designated Nationals (SDN) and consolidated European Union sanctions lists without identifying unapproved transactions.",
                "Export control classifications for encrypted software products were submitted to the US Bureau of Industry and Security (BIS) under Export Control Classification Numbers (ECCN) 5D002 and 5A002, obtaining formal Commodity Jurisdiction (CJ) determinations.",
            ]
        ),
        (
            "2. International Commercial Arbitration Seat Protocols and Lex Arbitri",
            [
                "Cross-border commercial joint venture agreements are governed by standardized dispute resolution provisions selecting London, England, or Geneva, Switzerland, as the neutral legal seat (lex arbitri) under the English Arbitration Act 1996 or Swiss Private International Law Act.",
                "Arbitral proceedings must be administered under the International Chamber of Commerce (ICC) Rules of Arbitration or London Court of International Arbitration (LCIA) Rules. Tripartite tribunals ensure neutral legal expertise, requiring the presiding arbitrator to hold extensive background in private international law and cross-border commercial contracts.",
                "Emergency arbitrator provisions under Appendix V of the ICC Rules guarantee rapid access to provisional conservatory measures, preventing dissipation of contested assets or breach of trade secret non-disclosure covenants during the pendency of tribunal constitution.",
            ]
        ),
        (
            "3. New York Convention Enforcement and Sovereign Immunity Waivers",
            [
                "All arbitral awards rendered by constituted tribunals are final, non-appealable on the merits, and mutually binding. The parties expressly consent to judgment recognition and judicial enforcement in any sovereign court of competent jurisdiction pursuant to the 1958 United Nations Convention on the Recognition and Enforcement of Foreign Arbitral Awards (The New York Convention).",
                "State-owned commercial counterparties execute express, irrevocable waivers of sovereign immunity regarding jurisdictional immunity, provisional injunctive attachments, and post-award asset execution pursuant to the Foreign Sovereign Immunities Act (FSIA) 28 U.S.C. Section 1605(a)(1).",
                "Judicial review grounds are strictly limited to the narrow procedural exceptions enumerated in Article V of the New York Convention, such as lack of proper arbitral notice or violation of public policy.",
            ]
        ),
        (
            "4. Regulatory Reporting, Whistleblower Protections, and Compliance Certifications",
            [
                "The chief compliance officer submits quarterly compliance certifications directly to the board audit committee. Confidential internal reporting channels and statutory whistleblower protections comply with Sarbanes-Oxley Section 806 and the EU Whistleblowing Directive 2019/1937.",
            ]
        )
    ]
    return title, sections


def get_tech_content_1():
    title = "DISTRIBUTED SYSTEMS ARCHITECTURE: EVENT-DRIVEN MICROSERVICES AND RAFT CONSENSUS"
    sections = [
        (
            "1. Event-Driven Microservices Topology and Asynchronous Messaging",
            [
                "This technical architectural specification outlines the distributed systems design for our next-generation cloud transaction processing platform. The architecture decomposes legacy monolithic services into decoupled, domain-driven microservices communicating over asynchronous event buses and high-throughput Apache Kafka clusters.",
                "Kafka topic partitions are sized to guarantee linear scalability, configured with a replication factor of 3 across distinct availability zones. Producers utilize idempotent write semantics (acks=all) to guarantee exactly-once message processing semantics without phantom records or payload duplications.",
                "Consumer group lag is continuously monitored via Prometheus telemetry exporters. When lag crosses a 5,000 message threshold, horizontal pod autoscalers (HPA) automatically spin up supplemental consumer instances in the Kubernetes cluster, maintaining 99.9th percentile event processing latency below 120 milliseconds.",
            ]
        ),
        (
            "2. Raft Consensus Protocol and Distributed Database Sharding",
            [
                "Distributed transactional state is synchronized using an optimized implementation of the Raft consensus protocol. The consensus engine handles leader election, log replication, and safe cluster reconfiguration in the presence of network partitions and node crash failures.",
                "Leader election cycles utilize randomized heartbeat election timeouts between 150ms and 300ms, minimizing split-vote scenarios. During network partitions, Raft prevents split-brain anomalies by requiring strict quorum majorities (N/2 + 1) before appending entries to the distributed state machine.",
                "Underlying relational data stores employ horizontal database sharding based on consistent hashing rings. Consistent hashing with virtual nodes ensures uniform data distribution and limits data migration overhead to 1/N partitions when adding storage capacity.",
            ]
        ),
        (
            "3. Zero-Trust Network Architecture, mTLS, and Service Mesh",
            [
                "Internal service-to-service communication is orchestrated through an Istio service mesh enforcing zero-trust network policies. Every inter-service HTTP/2 and gRPC call requires mutual TLS (mTLS) with SPIFFE cryptographic identity validation.",
                "Envoy sidecar proxies terminate and inspect encrypted traffic, enforcing granular authorization policies based on JSON Web Tokens (JWT) and Open Policy Agent (OPA) rule engines. Perimeter ingress controllers reject all non-compliant ciphers, mandating TLS 1.3 with ChaCha20-Poly1305 and AES-256-GCM cipher suites.",
                "Automated public key infrastructure (PKI) managed by HashiCorp Vault rotates short-lived X.509 certificates every 24 hours, mitigating the risk of compromised cryptographic credentials.",
            ]
        ),
        (
            "4. Disaster Recovery, Multi-Region Active-Active Failover, and Telemetry",
            [
                "The distributed platform maintains an active-active deployment footprint spanning three geographically separated cloud regions. Anycast BGP routing and distributed DNS load balancers route ingress traffic to the lowest-latency healthy datacenter.",
                "Continuous chaos engineering experiments run via Chaos Mesh inject latency, packet drop, and node failures to validate that the automated failover mechanisms satisfy Recovery Time Objectives (RTO < 30 seconds) and Recovery Point Objectives (RPO = 0).",
            ]
        )
    ]
    return title, sections


def get_tech_content_2():
    title = "CLOUD INFRASTRUCTURE BLUEPRINT: KUBERNETES, TERRAFORM, AND CI/CD PIPELINES"
    sections = [
        (
            "1. Declarative Infrastructure as Code (IaC) and Terraform Topologies",
            [
                "This technical blueprint describes the automated provisioning of multi-cloud enterprise infrastructure using Terraform and OpenTofu. Modular Infrastructure-as-Code (IaC) templates define Virtual Private Clouds (VPCs), subnets, transit gateways, and IAM role hierarchies across production and staging environments.",
                "Terraform state files are encrypted at rest using AWS KMS keys and stored in versioned S3 buckets protected by DynamoDB state locking to prevent concurrent deployment collisions. Automated CI/CD pipelines execute 'terraform plan' and run tfsec security linting on pull requests prior to merge approval.",
                "Network security topologies isolate sensitive database workloads in private non-routable subnets with egress routed strictly through redundant NAT Gateways and egress firewalls performing deep packet inspection.",
            ]
        ),
        (
            "2. Kubernetes Cluster Orchestration, Helm Charts, and GitOps Workflows",
            [
                "Container workloads run on managed Kubernetes (EKS / GKE) clusters utilizing custom node groups backed by AWS Graviton and AMD EPYC EC2 instances. Spot instances are tactically utilized for stateless batch processing, reducing compute overhead by 68%.",
                "Deployment manifests are managed via Helm v3 charts and synchronized continuously using ArgoCD GitOps controllers. ArgoCD monitors the infrastructure git repository, automatically reconciling cluster state against desired declarative configurations and rolling back failed deployments upon health check failure.",
                "Kubernetes resource limits, pod disruption budgets (PDB), and affinity rules prevent cluster node exhaustion and ensure high availability during scheduled worker node upgrades and cluster maintenance.",
            ]
        ),
        (
            "3. Continuous Integration and Continuous Deployment (CI/CD) Security",
            [
                "Software release pipelines automated through GitHub Actions enforce rigorous static application security testing (SAST), software composition analysis (SCA), and container image vulnerability scanning via Trivy and Snyk.",
                "Docker images are built with multi-stage minimal distroless base images, eliminating shell binaries and unnecessary operating system utilities to minimize the exploitable container attack surface.",
                "Images are cryptographically signed using Sigstore Cosign during CI builds. Kubernetes admission controllers (Kyverno) verify digital signatures before allowing container images to execute within production namespaces.",
            ]
        ),
        (
            "4. Observability, Distributed Tracing, and Log Aggregation",
            [
                "A unified observability stack combining Prometheus metrics, OpenTelemetry distributed tracing, and Grafana Loki log aggregation provides full-stack visibility across thousands of running container pods.",
                "Distributed trace contexts propagated through W3C TraceContext headers allow engineers to visualize end-to-end latency breakdowns across complex microservice call chains, identifying database query bottlenecks and API degradation in real time.",
            ]
        )
    ]
    return title, sections


def get_tech_content_3():
    title = "CYBERSECURITY THREAT MODEL AND PENETRATION TESTING ASSESSMENT"
    sections = [
        (
            "1. Threat Landscape, STRIDE Modeling, and Attack Surface Mapping",
            [
                "This comprehensive cybersecurity assessment articulates the threat modeling results and penetration testing findings for our enterprise cloud ecosystem. The threat model utilizes the Microsoft STRIDE methodology: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, and Elevation of Privilege.",
                "External attack surface mapping identified 142 exposed public endpoints, all protected by Web Application Firewalls (WAF) implementing OWASP Core Rule Sets. Rate limiting and bot management policies mitigate automated credential stuffing and brute-force authentication attacks.",
                "Internal architecture models privilege boundaries between DMZ web tiers, application microservices, and database persistence layers, verifying that network segmentation prevents lateral movement in the event of an individual perimeter host compromise.",
            ]
        ),
        (
            "2. Cryptographic Implementation, KMS Key Rotations, and Data Protection",
            [
                "Data at rest is encrypted across all storage volumes, S3 buckets, and RDS database snapshots using AES-256-XTS and envelope encryption orchestrated by Hardware Security Modules (HSM) certified to FIPS 140-2 Level 3 standards.",
                "KMS Customer Managed Keys (CMK) undergo automated annual cryptographic key rotations. Database columns containing sensitive PII and financial records are protected using application-level format-preserving encryption (FPE), preventing database administrators from viewing plaintext records.",
                "Data in transit mandates TLS 1.3 across all network interfaces, strictly prohibiting legacy SSLv3, TLS 1.0, and TLS 1.1 protocols. Perfect Forward Secrecy (PFS) using Ephemeral Elliptic Curve Diffie-Hellman (ECDHE) key exchange protects historical network traffic against retrospective decryption.",
            ]
        ),
        (
            "3. Penetration Testing Findings, Vulnerability Remediation, and Red Team Ops",
            [
                "Annual independent red team penetration testing evaluated the resilience of identity and access management (IAM), API endpoints, and cloud infrastructure. Testers identified zero Critical or High severity vulnerabilities across the external perimeter.",
                "Medium-severity findings, including Cross-Origin Resource Sharing (CORS) wildcard misconfigurations on staging subdomains and verbose error trace disclosures, were remediated and verified within seven business days under strict SLA protocols.",
                "Simulated spear-phishing campaigns conducted across internal workforce personnel achieved a 98.4% reporting rate, demonstrating high employee security awareness regarding social engineering tactics.",
            ]
        ),
        (
            "4. Incident Response Plan, SOC Operations, and Automated Threat Containment",
            [
                "The 24/7 Security Operations Center (SOC) utilizes an AI-assisted Security Information and Event Management (SIEM) platform ingesting over 50,000 security events per second from endpoints, cloud audit trails (CloudTrail), and VPC Flow Logs.",
                "Automated Security Orchestration, Automation, and Response (SOAR) playbooks isolate compromised host instances, revoke active IAM credentials, and block suspicious IP ranges within sub-second response windows, containing potential intrusions before data exfiltration occurs.",
            ]
        )
    ]
    return title, sections


def main():
    UNORGANISED_DIR.mkdir(exist_ok=True)

    files_to_generate = [
        # Education
        ("curriculum_standards_2026.txt", "txt", get_education_content_1),
        ("faculty_symposium_proceedings.docx", "docx", get_education_content_2),
        ("pedagogical_assessment_report.pdf", "pdf", get_education_content_3),

        # Finance
        ("quarterly_treasury_audit.txt", "txt", get_finance_content_1),
        ("consolidated_financial_statement.docx", "docx", get_finance_content_2),
        ("portfolio_risk_disclosure.pdf", "pdf", get_finance_content_3),

        # Law
        ("appellate_brief_in_re_tech.txt", "txt", get_law_content_1),
        ("master_services_agreement.docx", "docx", get_law_content_2),
        ("statutory_compliance_filing.pdf", "pdf", get_law_content_3),

        # Technology
        ("distributed_systems_architecture.txt", "txt", get_tech_content_1),
        ("cloud_infrastructure_blueprint.docx", "docx", get_tech_content_2),
        ("cybersecurity_threat_model.pdf", "pdf", get_tech_content_3),
    ]

    print(f"Generating {len(files_to_generate)} lengthy files in '{UNORGANISED_DIR}'...")

    for filename, ftype, content_fn in files_to_generate:
        target_path = UNORGANISED_DIR / filename
        title, sections = content_fn()
        if ftype == "txt":
            make_txt(target_path, title, sections)
        elif ftype == "docx":
            make_docx(target_path, title, sections)
        elif ftype == "pdf":
            make_pdf(target_path, title, sections)
        print(f"Created: {filename:<38} | Type: {ftype:<4} | Size: {target_path.stat().st_size} bytes")

    print("\nGeneration complete!")


if __name__ == "__main__":
    main()
