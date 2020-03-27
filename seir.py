import datetime
from datetime import timedelta
import matplotlib.pyplot as plt
import pandas as pd


class Seir(object):
    def __init__(self, params, start, dT=0.01):
        self.params = params
        self.start = start
        self.dT = dT

    def simulate(self, social_distancing_steps):
        # Convert policy steps to daily paths
        self.policy_path = self._steps_to_path(social_distancing_steps, dT=self.dT)

        # Initialize results with starting values
        self.results = {k: [v] for k, v in self.start.items()}
        self.results["T"] = [self.policy_path[0][0]]  # first date in policy path
        self.results["P"] = [self.policy_path[0][1]]  # first policy in policy path

        for time, social_distancing in self.policy_path:
            self.iterate(time=time, social_distancing=social_distancing)

    def iterate(self, time, social_distancing):
        """Iterate current state forward by one step with current social_distancing"""
        # Roll forward time
        time = time + timedelta(days=self.dT)

        # Retrieve parameters
        beta = self.params["beta"]
        t_incubation = self.params["t_incubation"]
        t_presymptomatic = self.params["t_presymptomatic"]
        t_recovery_asymptomatic = self.params["t_recovery_asymptomatic"]
        t_recovery_mild = self.params["t_recovery_mild"]
        t_recovery_severe = self.params["t_recovery_severe"]
        t_hospital_lag = self.params["t_hospital_lag"]
        t_death = self.params["t_death"]
        p_self_quarantine = self.params["p_self_quarantine"]
        p_asymptomatic = self.params["p_asymptomatic"]
        p_severe = self.params["p_severe"]
        p_fatal = self.params["p_fatal"]
        p_mild = 1 - p_asymptomatic - p_severe - p_fatal

        a = 1 / t_incubation
        gamma = 1 / t_presymptomatic  # but infectiuous

        T = self.results["T"][-1]
        S = self.results["S"][-1]
        E = self.results["E"][-1]
        I = self.results["I"][-1]
        I_asymptomatic = self.results["I_asymptomatic"][-1]
        I_mild = self.results["I_mild"][-1]
        I_severe_home = self.results["I_severe_home"][-1]
        I_severe_hospital = self.results["I_severe_hospital"][-1]
        I_fatal_home = self.results["I_fatal_home"][-1]
        I_fatal_hospital = self.results["I_fatal_hospital"][-1]
        R_from_asymptomatic = self.results["R_from_asymptomatic"][-1]
        R_from_mild = self.results["R_from_mild"][-1]
        R_from_severe = self.results["R_from_severe"][-1]
        Dead = self.results["Dead"][-1]

        # Flows this time increment

        # Not infected
        dS = (-beta * (1-social_distancing)**2 * (I + I_asymptomatic + (1-p_self_quarantine) * I_mild) * S) * self.dT

        # Non-infectiuous incubation time
        dE = (beta * (1-social_distancing)**2 * (I + I_asymptomatic + (1-p_self_quarantine) * I_mild) * S - a * E) * self.dT

        # Infectious incubation time
        dI = (a * E - gamma * I) * self.dT

        # Asymptomatic
        dI_asymptomatic = (
            p_asymptomatic * gamma * I - (1 / t_recovery_asymptomatic) * I_asymptomatic
        ) * self.dT

        # Mild
        dI_mild = (p_mild * gamma * I - (1 / t_recovery_mild) * I_mild) * self.dT

        # B: Severe course (two steps)
        dI_severe_home = (
            p_severe * gamma * I - (1 / t_hospital_lag) * I_severe_home
        ) * self.dT
        dI_severe_hospital = (
            (1 / t_hospital_lag) * I_severe_home
            - (1 / t_recovery_severe) * I_severe_hospital
        ) * self.dT

        # C: Fatal course (two steps)
        dI_fatal_home = (p_fatal * gamma * I - (1 / t_hospital_lag) * I_fatal_home) * self.dT
        dI_fatal_hospital = (
            (1 / t_hospital_lag) * I_fatal_home - (1 / t_death) * I_fatal_hospital
        ) * self.dT

        # Final flows from courses of illness into recovery or death
        dR_from_asymptomatic = ((1 / t_recovery_asymptomatic) * I_asymptomatic) * self.dT
        dR_from_mild = ((1 / t_recovery_mild) * I_mild) * self.dT
        dR_from_severe = ((1 / t_recovery_severe) * I_severe_hospital) * self.dT
        dDead = ((1 / t_death) * I_fatal_hospital) * self.dT

        # Storing simulated time self.results
        self.results["T"].append(time)
        self.results["P"].append(social_distancing)
        self.results["S"].append(S + dS)
        self.results["E"].append(E + dE)
        self.results["I"].append(I + dI)
        self.results["I_asymptomatic"].append(I_asymptomatic + dI_asymptomatic)
        self.results["I_mild"].append(I_mild + dI_mild)
        self.results["I_severe_home"].append(I_severe_home + dI_severe_home)
        self.results["I_severe_hospital"].append(I_severe_hospital + dI_severe_hospital)
        self.results["I_fatal_home"].append(I_fatal_home + dI_fatal_home)
        self.results["I_fatal_hospital"].append(I_fatal_hospital + dI_fatal_hospital)
        self.results["R_from_asymptomatic"].append(R_from_asymptomatic + dR_from_asymptomatic)
        self.results["R_from_mild"].append(R_from_mild + dR_from_mild)
        self.results["R_from_severe"].append(R_from_severe + dR_from_severe)
        self.results["Dead"].append(Dead + dDead)

    @property
    def data(self, resampling_rule="1d"):
        df = (
            pd.DataFrame.from_dict(self.results)
            .set_index("T")
            .resample(resampling_rule)
            .first()
            .assign(
                Hospitalized=lambda x: x["I_severe_hospital"] + x["I_fatal_hospital"],
                ICU=lambda x: x["Hospitalized"] * self.params["p_icu_given_hospital"],
                R_combined=lambda x: x["R_from_asymptomatic"] + x["R_from_mild"] + x["R_from_severe"],
                I_combined=lambda x: x["I"] + x["I_asymptomatic"] + x["I_mild"] + x["I_severe_home"] + x["I_severe_hospital"] + x["I_fatal_home"] + x["I_fatal_hospital"],
            )
            .rename(columns={"P": "Policy Strength"})
        )
        return df

    @staticmethod
    def _steps_to_path(social_distancing_steps, dT=1):
        """Convert dictionary of social_distancing steps to social_distancing path and associated dates"""
        dates = [datetime.datetime.fromisoformat(d) for d, _ in social_distancing_steps]
        social_distancings = [social_distancing for _, social_distancing in social_distancing_steps]
        date_path = []
        social_distancing_path = []
        for i, x in enumerate(dates[:-1]):
            length = int((dates[i + 1] - dates[i]).days / dT)
            dates_regime = [dates[i] + timedelta(days=dT * n) for n in range(length)]
            social_distancing_path_regime = [social_distancings[i]] * length
            date_path.extend(dates_regime)
            social_distancing_path.extend(social_distancing_path_regime)
        return list(zip(date_path, social_distancing_path))

    def plot_summary(self):
        data = self.data
        fig, ax = plt.subplots(2, 2, figsize=(12, 8))
        data[["Policy Strength"]].plot(ax=ax[0, 0])
        data[["S", "E", "I_combined", "R_combined"]].plot(ax=ax[0, 1])
        data[["Hospitalized", "ICU"]].plot(ax=ax[1, 0])
        data[["R_from_asymptomatic", "R_from_mild", "R_from_severe", "Dead"]].plot(
            ax=ax[1, 1]
        )
        for subplot in ax.reshape(-1):
            subplot.set_xlabel("")
        plt.show()
        return None