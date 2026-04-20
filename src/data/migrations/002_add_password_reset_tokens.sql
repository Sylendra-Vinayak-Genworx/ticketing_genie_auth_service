BEGIN;

CREATE TABLE IF NOT EXISTS auth.password_reset_tokens
(
    id         uuid                     NOT NULL DEFAULT gen_random_uuid(),
    user_id    uuid                     NOT NULL,
    token      character varying(64)    NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used       boolean                  NOT NULL DEFAULT false,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT password_reset_tokens_token_key UNIQUE (token),
    CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES auth.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token
    ON auth.password_reset_tokens (token);

CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id
    ON auth.password_reset_tokens (user_id);

END;
