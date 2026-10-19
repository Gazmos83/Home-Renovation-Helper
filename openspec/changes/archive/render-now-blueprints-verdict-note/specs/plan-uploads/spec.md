## ADDED Requirements

### Requirement: A confirmed plan keeps its images as blueprints
When the owner confirms a plan read, the service SHALL copy every PNG and JPEG uploaded to that conversation up to that turn into the house file as blueprints of the apartment the plan recorded, each with its original name, type and size. A blueprint SHALL be a file under the upload root and SHALL NOT be stored in the database. It SHALL outlive the conversation: deleting the conversation SHALL NOT delete it. Confirming a new plan read of the same apartment SHALL add its images and keep the earlier ones. An image already kept as a blueprint of that apartment SHALL NOT be kept twice. A declined plan SHALL keep nothing. The owner SHALL be able to list a room's blueprints (those of its apartment) and download each one through owner-gated routes. The download SHALL send the stored file as an attachment with its original type and `nosniff`. Without the session cookie both routes SHALL answer 401, and an unknown room or blueprint SHALL answer 404.

#### Scenario: Plan confirmed
- **WHEN** the owner attached `grundriss.png` and answered yes to the plan read of `Wohnung`
- **THEN** `Wohnung` has one blueprint `grundriss.png`, and listing the blueprints of its room `Wohnen` returns it

#### Scenario: Conversation deleted
- **WHEN** the conversation that carried `grundriss.png` is deleted
- **THEN** the blueprint of `Wohnung` is still listed and downloads

#### Scenario: Plan declined
- **WHEN** the owner answered no to the plan read
- **THEN** no blueprint is kept

#### Scenario: Plan read again
- **WHEN** the owner sends `grundriss-v2.png` in the same conversation and confirms a new plan read of `Wohnung`
- **THEN** `Wohnung` has two blueprints, `grundriss-v2.png` first, and `grundriss.png` is not kept twice
