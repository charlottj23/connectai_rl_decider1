
import connect_tycoon as ct


def test_env_episode_reward_equals_month_reward(company, brain):
    env = ct.CompanyEnv(company=company)
    obs, info = env.reset(options={"month_seed": 7000})
    total, steps, done = 0.0, 0, False
    while not done:
        d = env.decision
        a = ct.DEPTS[d.dept]["actions"].index(brain.act(d.dept, d.obs, d.ev))
        assert obs["action_mask"][a] == 1
        obs, r, done, trunc, info = env.step(a)
        total += r; steps += 1
    log, days = company.run_month(7000, brain)
    assert abs(total - sum(x["reward"] for x in log)) < 1e-9
    assert abs(info["month_profit"] - sum(d["profit"] for d in days)) < 1e-9


def test_jev_env_speaks_jev(company, brain):
    env = ct.JevEnv(company=company)
    req, info = env.reset(options={"month_seed": 7001})
    n = 0
    while req is not None:
        req, r, done, trunc, info = env.step(brain(req)); n += 1
    assert n > 300 and done


def test_gymnasium_registered():
    import gymnasium as gym
    env = gym.make("ConnectTycoon-v0")
    obs, info = env.reset(seed=1)
    assert env.observation_space.contains(obs)
    env.close()
