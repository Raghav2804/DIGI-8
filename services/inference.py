"""Conservative role-family and task hints inferred from job-title text.

These weak labels are derived from title wording. They are not source labels,
verified requirements, or a supervised model trained on ground-truth categories.
"""
import re

# Keep specific patterns before broad families so titles such as "AI product
# manager" or "e-commerce designer" are assigned to the most useful family.
RULES = [
    (r"\b(data scientist|machine learning|deep learning|ai engineer|artificial intelligence|nlp engineer|computer vision)\b", "Data & AI", ["machine learning", "Python", "AI"]),
    (r"\b(data engineer|analytics engineer|etl developer|data warehouse|business intelligence|power bi|tableau developer)\b", "Data & AI", ["data engineering", "SQL", "ETL", "analytics"]),
    (r"\b(business analyst|business consultant|management consultant|strategy consultant|process analyst)\b", "Business & Consulting", ["business analysis", "process improvement", "requirements gathering"]),
    (r"\b(data analyst|reporting analyst|research analyst|sql analyst)\b", "Data & AI", ["data analysis", "SQL", "reporting"]),
    (r"\b(cyber.?security|penetration tester|security analyst|security engineer|ethical hacker|soc analyst)\b", "IT & Cybersecurity", ["cybersecurity", "security testing", "risk analysis"]),
    (r"\b(devops|site reliability|cloud engineer|cloud architect|platform engineer|kubernetes|systems administrator|linux administrator)\b", "IT & Cloud", ["cloud infrastructure", "DevOps", "automation"]),
    (r"\b(qa|quality assurance|software tester|test automation|automation tester|manual tester|selenium tester)\b", "Software & QA", ["quality assurance", "software testing", "test automation"]),
    (r"\b(product manager|product owner|project manager|program manager|scrum master|agile coach|project coordinator)\b", "Product & Project Management", ["project management", "planning", "coordination"]),
    (r"\b(full stack|frontend|front.end|backend|back.end|software developer|software engineer|web developer|web development|mobile app developer|ios developer|android developer|python developer|java developer|javascript developer|wordpress|shopify developer|webflow developer|bubble developer)\b", "Software & Web", ["software development", "web development", "application development"]),
    (r"\b(ui.?ux|user experience|user interface|logo design|logo designer|graphic design|graphic designer|brand identity|illustrator|photoshop|product designer|web designer|interior designer)\b", "Design & Creative", ["visual design", "user experience design", "creative production"]),
    (r"\b(video editor|video editing|motion graphics|animator|3d artist|videographer|photographer|audio editor|voice.?over)\b", "Design & Creative", ["video production", "visual storytelling", "creative production"]),
    (r"\b(seo|search engine optimization|ppc|paid ads|google ads|facebook ads|social media|media buyer|digital marketing|content marketing|email marketing|growth marketer)\b", "Marketing & Sales", ["digital marketing", "campaign management", "audience growth"]),
    (r"\b(lead generation|appointment setter|sales representative|sales development|account executive|business development|cold caller|closer)\b", "Marketing & Sales", ["lead generation", "sales", "client outreach"]),
    (r"\b(copywriter|copywriting|content writer|technical writer|blog writer|article writer|ghostwriter|editor|proofreader|translator|translation|transcriptionist)\b", "Writing & Translation", ["writing", "editing", "content development"]),
    (r"\b(virtual assistant|administrative assistant|data entry|executive assistant|appointment scheduling|office manager|operations assistant|customer support assistant)\b", "Admin & Operations", ["administrative support", "coordination", "operations"]),
    (r"\b(bookkeeper|bookkeeping|accountant|accounting|financial analyst|payroll|quickbooks|tax preparer|financial controller)\b", "Finance & Accounting", ["accounting", "financial operations", "bookkeeping"]),
    (r"\b(customer service|customer support|technical support|help desk|call center|client support|customer success)\b", "Customer Support", ["customer service", "client support", "issue resolution"]),
    (r"\b(recruiter|recruiting|talent acquisition|hr manager|human resources|people operations)\b", "HR & Recruiting", ["recruiting", "talent sourcing", "human resources"]),
    (r"\b(lawyer|legal assistant|paralegal|legal researcher|contract attorney|compliance officer)\b", "Legal & Compliance", ["legal research", "document review", "compliance"]),
    (r"\b(tutor|teacher|instructor|course creator|curriculum developer| instructional designer|online educator)\b", "Education & Training", ["teaching", "learning support", "curriculum development"]),
    (r"\b(e.?commerce|amazon seller|amazon listing|etsy shop|product listing|shopify store|store manager)\b", "E-commerce", ["e-commerce operations", "product listings", "online retail"]),
    (r"\b(architect|architecture|autocad|cad designer|mechanical engineer|civil engineer|electrical engineer|structural engineer|interior design|3d modeling|solidworks)\b", "Engineering & Architecture", ["technical design", "engineering", "CAD"]),
]

COMPILED_RULES = [(re.compile(pattern, re.I), category, tags) for pattern, category, tags in RULES]


def infer_title_metadata(title):
    """Return one inferred family and broad title-derived task hints."""
    text = str(title or "").strip()
    for pattern, category, tags in COMPILED_RULES:
        if pattern.search(text):
            # Explicit title technologies can improve retrieval, but remain
            # weak hints: their appearance in the title does not prove a
            # complete required-skills list for the listing.
            explicit = [word for word in ("Python", "SQL", "Java", "JavaScript", "React", "AWS", "Azure", "Excel", "WordPress", "Shopify", "AutoCAD") if re.search(r"\b" + re.escape(word) + r"\b", text, re.I)]
            return category, list(dict.fromkeys(tags + explicit))
    return "Other", []
