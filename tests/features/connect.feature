Feature: JWS http basic test


  Scenario: Apache HTTPd welcome page is served
    When Container is started
    Then check that page is served on port "80"
