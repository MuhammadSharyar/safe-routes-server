pipeline {
    agent any // This specifies that the pipeline can run on any available agent

    stages {
        stage('Build') {
            steps {
                // This is where you define the steps for the 'Build' stage
                echo 'Building...'
                // You may run build commands or scripts here
            }
        }

        stage('Test') {
            steps {
                // This is where you define the steps for the 'Test' stage
                echo 'Testing...'
                // You may run test commands or scripts here
            }
        }

        stage('Deploy') {
            steps {
                // This is where you define the steps for the 'Deploy' stage
                echo 'Deploying...'
                // You may run deployment commands or scripts here
            }
        }
    }

    post {
        success {
            // This block is executed if the pipeline is successful
            echo 'Pipeline succeeded!'

            // You may trigger additional actions or notifications here
        }
        failure {
            // This block is executed if the pipeline fails
            echo 'Pipeline failed!'

            // You may trigger additional actions or notifications here
        }
    }
}
