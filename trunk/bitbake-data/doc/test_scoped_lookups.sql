BEGIN TRANSACTION;
CREATE TABLE recipes(id integer primary key, recipe text not null);
CREATE TABLE scope(id integer primary key, priority integer, scope_recipe_id integer, recipe_id integer);
CREATE TABLE vars(id integer primary key, var text, val text, recipe_id integer);

INSERT INTO "recipes" VALUES(NULL, 'bitbake.conf');
INSERT INTO "recipes" VALUES(NULL, 'base.bbclass');
INSERT INTO "recipes" VALUES(NULL, 'autotools.bbclass');
INSERT INTO "recipes" VALUES(NULL, 'a.bb');
INSERT INTO "recipes" VALUES(NULL, 'b.bb');

-- Attach scopes to base.bbclass, in this case only bitbake.conf and itself.
INSERT INTO "scope" VALUES(NULL, 2, 2, 2);
INSERT INTO "scope" VALUES(NULL, 1, 1, 2);

-- Attach scopes to autotools.bbclass, in this case bitbake.conf, base.bbclass, and itself.
INSERT INTO "scope" VALUES(NULL, 3, 3, 3);
INSERT INTO "scope" VALUES(NULL, 2, 2, 3);
INSERT INTO "scope" VALUES(NULL, 1, 1, 3);

-- Attach scopes to a.bb, in this case bitbake.conf, base.bbclass, and itself.
INSERT INTO "scope" VALUES(NULL, 3, 4, 4);
INSERT INTO "scope" VALUES(NULL, 2, 2, 4);
INSERT INTO "scope" VALUES(NULL, 1, 1, 4);

-- Attach scopes to a.bb, in this case bitbake.conf, base.bbclass, autotools.bbclass and itself.
INSERT INTO "scope" VALUES(NULL, 1, 1, 5);
INSERT INTO "scope" VALUES(NULL, 2, 2, 5);
INSERT INTO "scope" VALUES(NULL, 3, 3, 5);
INSERT INTO "scope" VALUES(NULL, 4, 5, 5);

-- Populate a variety of variables and values so that we can see what's happening.
INSERT INTO "vars" VALUES(NULL, 'CC', 'bitbake.conf_cc', 1);
INSERT INTO "vars" VALUES(NULL, 'CXX', 'bitbake.conf_cxx', 1);
INSERT INTO "vars" VALUES(NULL, 'CC', 'base.bbclass_cc', 2);
INSERT INTO "vars" VALUES(NULL, 'CC', 'autotools.bbclass_cc', 3);
INSERT INTO "vars" VALUES(NULL, 'CC', 'a.bb_cc', 4);
INSERT INTO "vars" VALUES(NULL, 'CC', 'b.bb_cc', 5);
INSERT INTO "vars" VALUES(NULL, 'CPP', 'b.bb_cpp', 5);

COMMIT;

-- Gets the highest priority value for 'CC', from base.bbclass and its scopes, by name

-- SELECT val FROM vars
-- JOIN scope ON vars.recipe_id = scope.scope_recipe_id
-- JOIN recipes ON scope.recipe_id = recipes.id
-- WHERE vars.var = 'CC' AND recipes.recipe = 'base.bbclass'
-- ORDER BY scope.priority DESC
-- limit 1;


-- Gets the highest priority value for 'CC', from a.bb and its scopes

-- SELECT val FROM vars
-- JOIN scope ON vars.recipe_id = scope.scope_recipe_id
-- WHERE vars.var = 'CC' AND scope.recipe_id = 4
-- ORDER BY scope.priority DESC
-- limit 1;


-- Gets the variable name and max priority for that variable, for each var

-- SELECT vars.var, MAX(scope.priority) FROM vars
-- JOIN scope ON vars.recipe_id = scope.scope_recipe_id
-- WHERE scope.recipe_id = 4
-- GROUP BY vars.var;


-- Gets all the variables, values, and priorities for a given recipe and its scopes
-- Includes all the values for a given var, not just the highest priority one, leaving
-- that piece in the hands of the C code.

-- SELECT vars.var, vars.val, scope.priority FROM vars
-- JOIN scope ON vars.recipe_id = scope.scope_recipe_id
-- WHERE scope.recipe_id = 4;


-- Get the highest priority value for each and every variable in a given
-- recipe and its scopes (not unlike running bbread on a .bb file)

-- SELECT vars.var, vars.val, scope.priority, maxes.max FROM vars, scope, recipes
-- JOIN (SELECT vars.var var, MAX(scope.priority) max
--       FROM vars, scope, recipes
--       WHERE vars.recipe_id = scope.scope_recipe_id AND
--       scope.recipe_id = recipes.id AND
--       recipes.recipe = 'b.bb'
--       GROUP BY vars.var) maxes ON vars.var = maxes.var
-- WHERE recipes.recipe = 'b.bb' AND
-- vars.recipe_id = scope.scope_recipe_id AND
-- scope.recipe_id = recipes.id AND
-- scope.priority = maxes.max;
