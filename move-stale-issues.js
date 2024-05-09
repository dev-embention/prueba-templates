const { request } = require('graphql-request');
const core = require('@actions/core');

const endpoint = 'https://api.github.com/graphql';

async function main(token) {
  const query = `
    query {
      repository(owner: "dev-embention", name: ${{ process.env.GITHUB_REPOSITORY }}) {
        projects(search: "Prueba CM", first: 1) {
          nodes {
            id
            columns(first: 10) {
              nodes {
                name
                id
              }
            }
          }
        }
        issues(labels: ["Stale"], first: 100) {
          nodes {
            id
            projectCards(first: 1) {
              nodes {
                id
              }
            }
          }
        }
      }
    }
  `;

  const mutation = `
    mutation($cardId: ID!, $columnId: ID!) {
      moveProjectCard(input: {cardId: $cardId, columnId: $columnId}) {
        clientMutationId
      }
    }
  `;

  const headers = {
    Authorization: `Bearer ${token}`
  };

  try {
    // Query projects and issues with stale label
    const data = await request(endpoint, query, null, headers);

    if (data.repository.projects.nodes.length === 0) {
      throw new Error("Project not found");
    }

    // Get the ID of the "Done" column
    const doneColumnId = data.repository.projects.nodes[0].columns.nodes.find(column => column.name === "Done").id;

    // For each issue, move the associated project card to the "Done" column
    for (const issue of data.repository.issues.nodes) {
      if (issue.projectCards.nodes.length > 0) {
        const cardId = issue.projectCards.nodes[0].id;
        await request(endpoint, mutation, { cardId, columnId: doneColumnId }, headers);
        console.log(`Moved project card for issue ${issue.id} to "Done" column`);
      }
    }
    core.setOutput('result', 'Success');
  } catch (error) {
    console.error('Error:', error.response ? error.response.errors : error.message);
    core.setFailed('Action failed');
  }
}

main(process.env.GITHUB_TOKEN);

fetchStaleIssuesAndMoveToDone();
