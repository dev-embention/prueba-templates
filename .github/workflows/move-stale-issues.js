const { Octokit } = require("@octokit/rest");

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});

async function fetchStaleIssuesAndMoveToDone() {
  try {
    const repo = process.env.GITHUB_REPOSITORY;
    // Step 1: Fetch all issues with the "stale" label
    const response = await octokit.issues.listForRepo({
      owner: "dev-embention",
      repo: repo,
      labels: "stale",
    });

    const staleIssues = response.data;

    // Step 2: Check if there are stale issues
    if (staleIssues.length > 0) {
      // Step 3: Update status in GitHub Projects to "Done"
      const projectColumns = await octokit.projects.listColumns({
        project_id: 2, // Replace with the ID of your GitHub Project
      });

      const doneColumn = projectColumns.data.find(
        (column) => column.name.toLowerCase() === "done"
      );

      if (doneColumn) {
        for (const issue of staleIssues) {
          await octokit.projects.createCard({
            column_id: doneColumn.id,
            content_id: issue.id,
            content_type: "Issue",
          });

          console.log(`Moved issue ${issue.number} to "Done" column.`);
        }
      } else {
        console.log("Error: 'Done' column not found.");
      }
    } else {
      console.log("No stale issues found.");
    }
  } catch (error) {
    console.error("Error:", error);
    throw error;
  }
}

fetchStaleIssuesAndMoveToDone();
