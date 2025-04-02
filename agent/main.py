import asyncio
from resume_loader import load_resume_data
from browser_computer import LocalPlaywrightComputer
from agent_config import create_agent
from form_filler import fill_basic_info, upload_resume, fill_demographics, fill_portfolio_and_linkedin, answer_open_ended_questions

async def main():
    resume = load_resume_data()
    job_url = "https://job-boards.greenhouse.io/deepmind/jobs/6293472"

    async with LocalPlaywrightComputer(job_url) as computer:
        await computer.page.wait_for_load_state("networkidle")
        print("✅ Page loaded")

        agent = create_agent(computer)

        await fill_basic_info(computer.page, resume)
        await upload_resume(computer.page)
        await fill_demographics(computer.page)
        await fill_portfolio_and_linkedin(computer.page, resume)
        await answer_open_ended_questions(computer.page, resume, job_url)

        print("\n✅ Finished filling form. Please review manually.")
        await computer.page.wait_for_timeout(10000)

if __name__ == "__main__":
    asyncio.run(main())