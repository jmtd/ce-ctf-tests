Feature: tomcat tests

  Scenario: check tomcat
    When container is ready
    Then check that page is served
       | property | value |
       | expected_status_code | 404 |
       | port     | 8080  |
       | wait     | 30    |
    And container log contains Server startup in
    And run echo AAA in container and check its output for AAA
    And /opt/webserver/LICENSE.txt should contain END OF TERMS AND CONDITIONS


  Scenario: check env and datasource
    When container is started with env
       | variable                  | value           |
       | DB_SERVICE_PREFIX_MAPPING | test-mysql=TEST |
       | TEST_DATABASE             | kitchensink     |
       | TEST_USERNAME             | marek           |
       | TEST_PASSWORD             | hardtoguess     |
       | TEST_MYSQL_SERVICE_HOST   | 10.1.1.1        |
       | TEST_MYSQL_SERVICE_PORT   | 3306            |
    Then /opt/webserver/conf/context.xml should contain <Resource name="jboss/datasources/test_mysql" auth="Container" type="javax.sql.DataSource" username="marek" password="hardtoguess" driverClassName="com.mysql.jdbc.Driver" url="jdbc:mysql://10.1.1.1:3306/kitchensink" maxActive="100" maxWait="10000" maxIdle="30"/>


  Scenario: check sti build
    Given sti build https://github.com/jboss-openshift/openshift-examples from binary
    Then container log contains Deploying web application archive \/opt\/webserver\/webapps\/node-info.war