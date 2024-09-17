import requests
import datetime

# Configura tu token personal de GitHub y la URL del endpoint de GraphQL
GITHUB_TOKEN = os.environ['TOKEN']
GITHUB_API_URL = 'https://api.github.com/graphql'
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# La query para obtener las issues del proyecto de una organización por su nombre
QUERY_PROJECT_BY_ORG = """
query($organization: String!, $projectNumber: Int!) {
  organization(login: $organization) {
    projectV2(number: $projectNumber) {
      id
      title
      field(name: "Status") {
        __typename
          ... on ProjectV2SingleSelectField {
            id
            options {
                id
                name
            }
          }
      }
      items(first: 100) {
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
            }
          }
          content {
            ... on Issue {
              id
              number
              title
              body
              state
              comments(last: 1) {
                nodes {
                  author {
                    login
                  }
                  body
                  createdAt
                }
              }
            }
          }
        }
      }
    }
  }
}

"""


# Función para hacer la solicitud GraphQL a GitHub
def run_query(query, variables):
    response = requests.post(
        GITHUB_API_URL,
        json={'query': query, 'variables': variables},
        headers=HEADERS
    )
    # Imprimimos el código de estado y la respuesta para ver qué está fallando
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    # Si no hay un status code 200, lanza una excepción con el mensaje de error
    if response.status_code != 200:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")

    result = response.json()

    # Si hay un campo 'errors' en la respuesta, lo imprimimos
    if 'errors' in result:
        print(f"Errors: {result['errors']}")
        raise Exception(f"Query failed with errors: {result['errors']}")

    return result


# Función para mover la issue a una columna del proyecto
def move_issue_to_column(card_id, column_id):
    mutation = """
    mutation($cardId: ID!, $columnId: ID!) {
      updateProjectV2ItemFieldValue(input: {itemId: $cardId, fieldId: $columnId}) {
        clientMutationId
      }
    }
    """
    variables = {"cardId": card_id, "columnId": column_id}
    result = run_query(mutation, variables)
    return result


# Función para agregar un comentario a una issue
def add_issue_comment(issue_number, comment_body):
    mutation = """
    mutation($issueId: ID!, $body: String!) {
      addComment(input: {subjectId: $issueId, body: $body}) {
        commentEdge {
          node {
            id
            body
          }
        }
      }
    }
    """
    variables = {"issueId": issue_number, "body": comment_body}
    result = run_query(mutation, variables)
    return result


# Función para cerrar una issue
def close_issue(issue_number):
    mutation = """
    mutation($issueId: ID!) {
      closeIssue(input: {issueId: $issueId}) {
        issue {
          closed
        }
      }
    }
    """
    variables = {"issueId": issue_number}
    result = run_query(mutation, variables)
    return result


# Función para obtener el ID de las columnas (esto lo puedes hacer una vez y reutilizar)
def get_project_columns(project_id):
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          views(first: 10) {
            nodes {
              id
              name
            }
          }
        }
      }
    }
    """
    variables = {"projectId": project_id}
    result = run_query(query, variables)

    # Extraer las columnas o vistas del proyecto
    columns = result['data']['node']['views']['nodes']
    return {col['name']: col['id'] for col in columns}


# Función para verificar si un usuario es miembro de la organización
def is_org_member(organization, username):
    url = f"https://api.github.com/orgs/{organization}/members/{username}"
    response = requests.get(url, headers=HEADERS)

    # Un código 204 significa que el usuario es miembro de la organización
    if response.status_code == 204:
        return True
    # Un código 404 significa que el usuario no es miembro de la organización
    elif response.status_code == 404:
        return False
    else:
        raise Exception(f"Failed to check membership for user {username}. Status code: {response.status_code}")


def update_project_item_status(project_id, item_id, field_id, field_value):
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $fieldValue: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: {
            singleSelectOptionId: $fieldValue
          }
        }
      ) {
        projectV2Item {
          id
        }
      }
    }
    """

    variables = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "fieldValue": field_value  # Aquí pasas el valor correspondiente, por ejemplo, "Answered" o "Done"
    }

    result = run_query(mutation, variables)
    return result

# Función principal que procesa las issues del proyecto
def process_issues(organization, project_number):
    variables = {"organization": organization, "projectNumber": project_number}
    data = run_query(QUERY_PROJECT_BY_ORG, variables)

    project = data['data']['organization']['projectV2']
    project_id = project['id']


    # Obtener los IDs de las columnas del proyecto
    columns = get_project_columns(project_id)

    # Asignamos las columnas de nuestro proyecto a variables
    columns_project = project['field'] ['options']
    array_legth = len(columns_project)

    for col in range(array_legth):
        if columns_project[col]['name'] == "Answered":
            column_answered_id = columns_project[col]['id']
        elif columns_project[col]['name'] == "Not Answered":
            column_not_answered_id = columns_project[col]['id']
        elif columns_project[col]['name'] == "Done":
            column_done_id = columns_project[col]['id']

        col += 1

    field_status_id = project['field'] ['id'] # Obtenemos el ID del campo 'Status'


    issues = project['items']['nodes']

    for issue in issues:
        issue_number = issue['content']['id']
        card_id = issue['id']  # El ID del item dentro del proyecto, que actúa como la tarjeta
        item_id = issue['id']  # El ID del item dentro del proyecto (la tarjeta)

        # Imprimir los valores de campo para depurar
        print(f"Issue #{issue_number} Field Values: {issue['fieldValues']['nodes']}")

        # Obtener el estado de la issue dentro del proyecto (campo status)
        status_field = next(
            (field for field in issue['fieldValues']['nodes'] if
             'field' in field and field['field']['name'] == 'Status'),
            None
        )

        if status_field:
            project_status = status_field['name']
        else:
            print(f"Issue #{issue_number} no tiene un campo de estado 'Status'. Saltando...")
            continue

        # Obtener el último comentario de la issue, si existe
        last_comment = issue['content']['comments']['nodes'][-1] if issue['content']['comments']['nodes'] else None

        if last_comment:
            comment_author = last_comment['author']['login']
            comment_date = datetime.datetime.strptime(last_comment['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
            # Verificar si el autor es miembro de la organización
            is_member = is_org_member(organization, comment_author)

        now = datetime.datetime.utcnow()
        # Caso A: Si está "Answered"
        if project_status == "Answered" and last_comment:
            if is_member and (now - comment_date).days >= 7 :
                add_issue_comment(issue_number, "This issue is stale because it has been open 15 days with no activity. Comment or this will be closed in 7 days.")
                update_project_item_status(project_id, item_id, field_status_id, column_done_id)

        # Caso B: Si está "Not Answered"
        elif project_status == "Not Answered" and last_comment:
            if is_member:
                update_project_item_status(project_id, item_id, field_status_id, column_answered_id)

        # Caso C: Si está "Done"
        elif project_status == "Done" and last_comment:
            if (now - comment_date).days >= 21:
                #add_issue_comment(issue_number, "Issue has been marked as done after 7 days without response.")
                close_issue(issue_number)


if __name__ == "__main__":
    # Reemplaza con la organización y el número del proyecto que deseas procesar
    organization = "dev-embention"
    project_number = 2  # Número del proyecto dentro de la organización
    process_issues(organization, project_number)
