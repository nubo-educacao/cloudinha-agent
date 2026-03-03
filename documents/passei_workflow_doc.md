# PRD & Documentação Técnica: Passaporte de Eligibilidade

## 1. Visão Geral (Goal)
O **Passaporte de Eligibilidade** é o guia definitivo para o processo de aplicação de estudantes a programas educacionais através do *Passaporte da Eligibilidade*. Ele atua como um assistente tira-dúvidas e direcionador de componentes UI, garantindo que o usuário complete sua aplicação no programa educacional ideal de forma fluida e sem atritos.

A Cloudinha atua como uma **"Recrutadora Parceira e Empática"** que atua como um concierge para o estudante e um filtro qualificado para a instituição.

O **Passaporte de Elegibilidade** elimina a necessidade de o estudante decifrar editais. A Cloudinha entrevista, valida e preenche os dados. O parceiro recebe não apenas um "lead", mas uma **candidatura estruturada** e validada.

1) Ler o estado atual dos dados do usuário usando getStudentProfile, para saber com quem está falando,  se onboarding_completed = TRUE e  qual sua passport_phase
2) A cada mensagem enviada a Cloudinha deve estar orientada a informar sobre o passo atual que o estudante está no processo de aplicação ou usar ferramentas para tirar dúvidas e orientar o estudante no que for preciso, de acordo com o que o usuário estiver perguntando. Ela não deve falar sobre outros assuntos ou gerar respostas sobre outros assuntos
3) Ela sempre poderá usar uma das ferramentas para responder dúvidas, mas deve focar em orientar e direcionar o usuario a seguir o fluxo e responder o formulário (que está acontecendo no Painel de Conteúdo ao lado). As ferramentas que ela pode usar são 

smartResearch.py
 (identificando se a dúvida/target_program é sobre o passaporte, o prouni, o sisu, a cloudinha, ou programas de apoio educacional) e 

getImportantDates.py
s (sobre/program type = prouni, sisu, general, partners -  programas educacionais parceiros)
4) Na primeira mensagem enviada, todos os usuários terão passaport_phase = INTRO
 5) Enquanto estiver com esse estado, a Cloudinha (passei_workflow) deve explicar que "Estou aqui para te ajudar a encontrar oportunidades educacionais que combinem com o seu momento e seus objetivos.
Você pode conhecer e se candidatar a programas de apoio educacional. Esses programas ajudam estudantes a desenvolver seu potencial ao longo da trajetória escolar. Eles podem oferecer aulas complementares, mentoria, orientação de estudos, desenvolvimento pessoal e, em alguns casos, apoio financeiro.
Estou aqui para responder qualquer dúvida que você tiver sobre programas educacionais e sobre o processo de aplicar na plataforma. Para começar, preciso entender um pouco sobre você.  Comece preenchendo o Onboarding ao lado. Com esses dados vamos te indicar em quais programas parceiros que você pode se aplicar"
6) No frontend (

nubo-hub-app
), enquanto houver essa passport_phase, ficamos sem componente de UI (avatar da Cloudinha de placeholder) e com o 

ChatInput.tsx
 bloqueado. 
7) 5 segundos depois do usuário entrar na tela deve mudar a phase para ONBOARDING, destravar o ChatInput e renderizar o componente de UI 

UserDataSection.tsx
, com o user_profile do usuário logado. Caso não tenha user_profile, deve haver um POST
8) Quando o usuario terminar de preencher irá mudar a passport_phase para ASK_DEPENDENT
9) Ao mudar essa phase ficamos sem componente de UI (avatar da Cloudinha de placeholder)
10) Nessa etapa a Cloudinha deverá perguntar se a pessoa está buscando uma oportunidade para ela própria ou outra pessoa (lembre-se que o 

getStudentProfile.py
 está sendo chamado antes de toda pergunta, então ela sabe a idade da pessoa) e usar a 

processDependentChoice.py
.
11) Se is_dependent = FALSE  chama evaluatePassportEligibilityTool e atualiza para phase EVALUATE
12) Se is_dependent = TRUE cria 1 o novo user_profiles e atualiza para phase DEPENDENT_ONBOARDING
13) Nessa phase deve aparecer o DependentDataSection, que deve ser uma cópia do UserDataSection mas com 1 campo de Grau de parentesco e o nome dos campos atualizados
14) Quando finalizar esse formulário e salvar chama evaluatePassportEligibilityTool com os dados do dependente e atualiza phase para PROGRAM_MATCH
15) Na phase PROGRAM_MATCH também fica a imagem placeholder e input travado. A Tool anterior deve fornecer informação de quantos critérios de eligibilidade o usuário ou seu dependente já se adequam em relação a  cada partner (programa parceiro)
16) Nela o agente deve instigar o estudante a saber mais sobre os programas, principalmente o que ele se adequa mais e se aplicar usando o Passaporte da Eligibilidade. Pela conversa ele identificar qual programa o estudante quer seguir e chamar uma startStudentApplicationTool, fazendo POST student_application com partner_id = do partner que ele escolher e já pré-preenchendo a student_application com as informações que temos em user_preferences e user_profiles, usando a partner_forms.mapping_source
17) A cloudinha deve confirmar com o usuário antes de usar essa Tool e depois de usar deve alterar a phase para EVALUATE
18) Na phase EVALUATE vamos precisar de um novo componente de UI renderizando o partner_forms correspondente, seguindo a ordem dos partner_steps (verifique 

PartnerForm.tsx
e 

PartnerFormsManager.tsx
para entender coimo os partnerforms sao construidos)
19) Nessa fase a Cloudinha deve estar orientada a tirar dúvidas sobre os editais e processo daquele partner específico usando a 

smartResearch.py
e a incentivar a finalizar o formulário
20) Quando finalizar e clicar em Concluir, deve ser alterado o status da student_appliaction e salvar as informações de user_preferences e user_profiles a partir da mapping_source
21) Deve trocar a PHASE para CONCLUDED e mostrar novamente o placeholder da Cloudinha
22) Nessa fase o agente pode continuar tirando duvidas usando as ferramentas de busca, mas não usará outras ferramentas que interagem com o banco de dados