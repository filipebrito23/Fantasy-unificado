-- Adicionar coluna sigla
ALTER TABLE teams ADD COLUMN sigla VARCHAR(10);

-- Atualizar com as siglas
UPDATE teams SET sigla = 'ABB' WHERE team_name = 'Alabama Black Bears';
UPDATE teams SET sigla = 'FRC' WHERE team_name = 'Franca Celtics';
UPDATE teams SET sigla = 'GUA' WHERE team_name = 'Guarulhos Nuggets';
UPDATE teams SET sigla = 'IRB' WHERE team_name = 'Itajubá Rabbits';
UPDATE teams SET sigla = 'KDG' WHERE team_name = 'Kaipiras da Gema';
UPDATE teams SET sigla = 'MIB' WHERE team_name = 'Miami Barons';
UPDATE teams SET sigla = 'MNT' WHERE team_name = 'Montreal Turtles';
UPDATE teams SET sigla = 'NOD' WHERE team_name = 'New Orleans Dancers';
UPDATE teams SET sigla = 'OSA' WHERE team_name = 'Osasco Heat';
UPDATE teams SET sigla = 'PVK' WHERE team_name = 'Pelotas Vikings';
UPDATE teams SET sigla = 'PER' WHERE team_name = 'Pernambuco Pharynx';
UPDATE teams SET sigla = 'RBD' WHERE team_name = 'RJ Black Mamba';
UPDATE teams SET sigla = 'RBM' WHERE team_name = 'Recife Black Diamond';
UPDATE teams SET sigla = 'TCH' WHERE team_name = 'Tchêltics da Peleia';