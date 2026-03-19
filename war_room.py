import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
import time
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tasks.task_output import TaskOutput
from langchain_core.tools import Tool
from duckduckgo_search import DDGS

# ── PRODUCTION FAILSAFES ──
os.environ["LITELLM_MAX_RETRIES"] = "1" 

# Bucket A: Llama 3.1 8B - Fast Grunt Workers
llm_fast = LLM(
    model="groq/llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

# Bucket B: Llama 3.3 70B - Strategic Heavy Hitters
llm_heavy = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2
)

def perform_live_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=2)
            if not results: return "No breaking news found."
            return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except:
        return "Web search currently unavailable."

web_search_tool = Tool(
    name="Web Search Tool",
    func=perform_live_search,
    description="Searches the live internet for corporate news or strikes."
)

def throttle_api(output: TaskOutput):
    """Pauses 12s between tasks to reset Groq TPM limits."""
    time.sleep(12)

def run_legal_war_room(user_message: str, retrieved_laws: str) -> str:
    import logging
    logging.getLogger("karma-claims").info("War Room activated.")

    if "MANDATORY LEGAL FRAMEWORK" in user_message:
        pure_user_story = user_message.split("MANDATORY LEGAL FRAMEWORK")[0]
        injected_laws = user_message.split("MANDATORY LEGAL FRAMEWORK")[1]
    else:
        pure_user_story = user_message
        injected_laws = retrieved_laws

    safe_laws = injected_laws[:4000]

    # ── THE AGENTS ──
    extractor = Agent(
        role="Case Intake Paralegal",
        goal="Extract facts: Primary Target Company, Amount, Order ID, and a DETAILED Core Narrative.",
        backstory="You extract the facts. CRITICAL: You must clearly separate the 'Primary Target' (who the user is fighting) from any 'Third-Party Merchants' mentioned. If the user mentions corporate excuses (like 'we are just an intermediary'), include those exact quotes, but clearly state WHO made the excuse.",
        llm=llm_fast, 
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    rag_specialist = Agent(
        role="Statutory Compliance Officer",
        goal="Identify 2 specific legal violations from the provided legal vault text.",
        backstory="You match the user's pain to the strict word of the law.",
        llm=llm_fast, 
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    web_counseller = Agent(
        role="Live Intelligence Analyst",
        goal="Check for company outages, news, or strikes related to the target company.",
        backstory="You find the 'Why' behind the failure using web search.",
        tools=[web_search_tool],
        llm=llm_heavy, 
        max_iter=2,
        verbose=True,
        allow_delegation=False
    )

    defender = Agent(
        role="Corporate Defense Attorney",
        goal="Predict 1 common corporate excuse the company will use to stall.",
        backstory="You play devil's advocate to help the user prepare for resistance.",
        llm=llm_fast,
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    victory_strategist = Agent(
        role="Victory Probability Analyst",
        goal="Assess the user's realistic chances of winning and identify the single strongest leverage point in their case.",
        backstory="""You are a senior consumer law analyst who has studied thousands of Indian consumer forum judgements.
        You think in terms of WIN CONDITIONS.
        Your job is to answer 3 questions:
        1. STRENGTH SCORE: Rate this case 1-10 for likelihood of winning at consumer forum. Be honest.
        2. STRONGEST WEAPON: What is the single most powerful fact or law in the user's favor? (e.g., "The company's own reply email admits the delay — this is a written confession of deficiency in service.")
        3. WEAK POINT: What is the one thing that could hurt the user's case? What should they NOT say or do?
        Keep each answer to 1-2 sentences. Be brutally honest — a user who knows their weak points wins more than one who is blindly confident.""",
        llm=llm_heavy,
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    escalation_mapper = Agent(
        role="Post-Strike Escalation Architect",
        goal="Map the exact next steps the user must take if the company ignores, rejects, or lowballs the legal notice.",
        backstory="""You are a procedural expert in Indian consumer grievance escalation.
        You know every portal, every deadline, every fee, and every regulator.
        Based on the sector and company identified, you must provide:
        1. THE 30-DAY PLAN: A specific day-by-day action plan after the notice is sent.
           - Day 1-7: What to do if the company calls.
           - Day 8-15: What to do if there is no response.
           - Day 16-30: Final warning email + filing preparation.
           - Day 30+: File on e-Daakhil. Exact URL, exact fee, exact form needed.
        2. SECTOR-SPECIFIC REGULATOR: The exact government portal for this sector (e.g., RBI Ombudsman for banking, DGCA AirSewa for airlines, IRDAI Bima Bharosa for insurance).
        3. NUCLEAR OPTION: If e-Daakhil fails, what is the next step? (State Commission, National Commission, or sector regulator's tribunal.)
        Be specific. Give real URLs. Give real deadlines. This is what converts a legal notice into a real WIN.""",
        llm=llm_heavy,
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    chief = Agent(
        role="The Sovereign Sentinel (Chief Litigator)",
        goal="Draft a ruthless, undeniable pre-litigation legal notice.",
        backstory="""You are an elite Supreme Court Litigator specializing in corporate accountability.
        STRICT RULES: 
        1. TONE: Cold, authoritative, and legally devastating. Use heavy statutory terminology.
        2. FORMAT: 4 paragraphs. End the notice immediately after the 'Prayer for Relief'. DO NOT write a 'Subject:' line inside the notice body. Start directly with 'To [Company Name],'. You MUST end the notice with exactly this signature block and nothing else: "Sincerely, [YOUR_NAME_HERE], [YOUR_PHONE_HERE]".
        2d. CEO ADDRESSING: If a CEO name is available from the case facts, open the notice with: 'To [Company Name], For the attention of [CEO Name],' — this ensures the notice is personally addressed and cannot be dismissed by Level 1 support.
        2b. PERSON: Write in FIRST PERSON throughout. Use "I" not "the consumer". Example: "I demand" not "The consumer demands". "I hereby serve" not "This notice is served".
        2c. LAW CITATION FORMAT: Always write the full proper name of the Act or Rule. NEVER use filenames, underscores, or shorthand. Write "Consumer Protection (E-Commerce) Rules, 2020" not "ECommerce_Rules_2020". Write "Rule 4" not "Section (4)" when citing E-Commerce Rules.
        3. THE BURDEN OF PROOF TRAP: If the issue involves an app, website, or digital payment failure, explicitly state that the company maintains "backend server logs, clickstream data, and API telemetry." Demand they audit their own systems instead of illegally shifting the burden of proof onto the consumer.
        4. THE PENALTY: Demand the exact original disputed amount PLUS a proportionate statutory penalty for mental agony (e.g., 20% to 50% of the disputed amount). NEVER blindly demand ₹50,000 unless the disputed amount is massive.
        5. ANTI-HALLUCINATION LOCK — THIS IS YOUR MOST IMPORTANT RULE:
           - NEVER write a section number you were not explicitly given by the Compliance Officer.
           - If the Compliance Officer gave you "Section 2(11)", write "Section 2(11)". Do not change it.
           - If you are unsure of a section number, write the ACT NAME ONLY (e.g., "Consumer Protection Act, 2019") without any section number.
           - A notice with no section number is FAR BETTER than a notice with a wrong section number.
           - FORBIDDEN: Making up sections like "Section 14(2)(b)" or "Section 47A" that were not in your briefing.""",

        llm=llm_heavy,
        max_iter=1,
        verbose=True,
        allow_delegation=False
    )

    # ── TASKS ──
    t1 = Task(
        description=f"Extract facts and core narrative: {pure_user_story}",
        expected_output="Bullet list: Primary Target Company, Amount, ID, and a detailed 3-sentence Core Issue that clearly explains what the Primary Target did wrong without confusing them with third-party merchants.",
        agent=extractor,
        callback=throttle_api
    )

    t2 = Task(
        description=f"Find 2 violations in these laws: {safe_laws}",
        expected_output="2 bullet points of statutory violations.",
        agent=rag_specialist,
        context=[t1],
        callback=throttle_api
    )

    t3 = Task(
        description="""You have TWO missions using web search:

        MISSION 1 — LAW UPGRADE SEARCH:
        The Compliance Officer found these laws from the internal vault (Task 2).
        Search the web to find if there is a STRONGER or more SPECIFIC law, section, or clause
        for this exact type of consumer dispute.
        Search for: "[issue type] India consumer law section 2024 2025"
        Search for: "[company name] NCDRC judgement penalty consumer forum"
        If you find a better clause or a real court judgement, name it precisely.
        Output it as: "PROPOSED UPGRADE: [exact act name, section number, and why it is stronger]"
        If nothing better exists, output: "VAULT LAWS CONFIRMED: No stronger provision found."

        MISSION 2 — COMPANY INTELLIGENCE:
        Search for recent news, regulator penalties, or complaint patterns about the target company.
        A regulator fine against this company = nuclear leverage in the notice.""",
        expected_output="""Two sections:
        LAW UPGRADE PROPOSALS:
        - Either "PROPOSED UPGRADE: [Act, Section, reason it is stronger]" for each improvement found
        - Or "VAULT LAWS CONFIRMED: No stronger provision found."

        COMPANY INTELLIGENCE:
        - Bullet points of any regulator actions, penalties, or complaint patterns found.
        - If nothing found: "No recent actions found." """,
        agent=web_counseller,
        context=[t1, t2],
        callback=throttle_api
    )

    t3b = Task(
        description="""The Live Intelligence Analyst (Task 3) has proposed law upgrades from the web.
        Your job is to go back into the legal vault and VERIFY each proposed upgrade.

        For each "PROPOSED UPGRADE" from Task 3:
        1. Search the vault text you were given for that exact act, section, or clause.
        2. If you find it in the vault — mark it "VAULT VERIFIED: [section] — confirmed present and applicable."
        3. If it is NOT in the vault but the section name is real and well-known Indian law — mark it "ACCEPTED ON STATUTORY GROUNDS: [section] — not in vault but is established Indian law."
        4. If you cannot verify it at all — mark it "REJECTED: [section] — could not verify, do not use."

        Also confirm which of the original Task 2 laws should still be used alongside any upgrades.

        OUTPUT THE FINAL APPROVED LAW LIST — this is what the Chief Litigator will use.
        Nothing goes into the legal notice unless it appears in this approved list.""",
        expected_output="""FINAL APPROVED LAW LIST:
        - [Law 1]: VAULT VERIFIED / ACCEPTED ON STATUTORY GROUNDS / REJECTED — [1 sentence reason]
        - [Law 2]: VAULT VERIFIED / ACCEPTED ON STATUTORY GROUNDS / REJECTED — [1 sentence reason]
        - [Any upgrades from Task 3 that passed verification]

        INSTRUCTION TO CHIEF: Use ONLY the laws marked VAULT VERIFIED or ACCEPTED ON STATUTORY GROUNDS.
        Discard all REJECTED entries.""",
        agent=rag_specialist,
        context=[t2, t3],
        callback=throttle_api
    )

    t4 = Task(
        description="Predict the corporate stall tactic based on the findings.",
        expected_output="One sentence corporate excuse.",
        agent=defender,
        context=[t2, t3, t3b],
        callback=throttle_api
    )

    t5 = Task(
        description="Analyze the case strength and identify the single strongest leverage point and the single biggest weak point.",
        expected_output="""Exactly 3 sections:
        STRENGTH SCORE: [X/10] — [1 sentence reason]
        STRONGEST WEAPON: [1-2 sentences — the most powerful fact or law in the user's favor]
        WEAK POINT: [1-2 sentences — what could hurt the case and what the user must NOT do]""",
        agent=victory_strategist,
        context=[t1, t3b, t3, t4],
        callback=throttle_api
    )

    t6 = Task(
        description="Build the 30-day post-notice action plan and identify the exact sector regulator portal for this case.",
        expected_output="""Exactly 2 sections:
        30-DAY BATTLE PLAN:
        - Day 1-7: [specific action]
        - Day 8-15: [specific action]
        - Day 16-30: [specific action]
        - Day 30+: File on e-Daakhil — edaakhil.nic.in — [exact form and fee]
        SECTOR REGULATOR: [Name of portal, exact URL, and what to file there]""",
        agent=escalation_mapper,
        context=[t1, t3b],
        callback=throttle_api
    )

    t7 = Task(
        description="""Draft the final Pre-Litigation Legal Notice.

        CRITICAL — YOUR ONLY SOURCE FOR LAWS IS TASK 3b's FINAL APPROVED LAW LIST.
        DO NOT use any law that is marked REJECTED in Task 3b.
        USE ONLY laws marked VAULT VERIFIED or ACCEPTED ON STATUTORY GROUNDS.
        If Task 3 found a real court judgement or regulator penalty — cite it by name.

        Integrate: facts from Task 1, approved laws from Task 3b, destroy the excuse from Task 4.
        After the notice body, add a section called '⚔️ YOUR BATTLE INTELLIGENCE' that includes:
        - The victory analysis from Task 5 (strength score, weapon, weak point)
        - The 30-day plan from Task 6
        This turns the output into a complete battle package, not just a notice.""",
        expected_output="""Two clearly separated sections:
        SECTION 1 — LEGAL NOTICE: Final 4-paragraph notice. No signature block. Ends after Prayer for Relief.
        SECTION 2 — ⚔️ YOUR BATTLE INTELLIGENCE: Strength score, strongest weapon, weak point, and the 30-day plan.""",
        agent=chief,
        context=[t1, t3b, t3, t4, t5, t6]
    )

    crew = Crew(
        agents=[extractor, rag_specialist, web_counseller, defender, victory_strategist, escalation_mapper, chief],
        tasks=[t1, t2, t3, t3b, t4, t5, t6, t7],
        process=Process.sequential,
        verbose=True
    )

    result = crew.kickoff()
    return str(result)