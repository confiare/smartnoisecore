import os
from distutils.util import strtobool

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sys

# os.environ['WN_DEBUG'] = '1'
# os.popen("python /Users/ethancowan/IdeaProjects/whitenoise-core-python/scripts/code_generation.py").read()
# np.set_printoptions(threshold=sys.maxsize)

import opendp.smartnoise.core as sn
from tests import TEST_PUMS_PATH, TEST_PUMS_NAMES

IS_CI_BUILD = strtobool(os.environ.get('IS_CI_BUILD', 'False'))


def get_loss(data, params):
    # individuals x 1
    actual = data[:, 0]
    actual.shape += (1,) * (2 - actual.ndim)
    data = data.copy()
    data[:, 0] = 1.
    # individuals x iterations
    predicted = 1 / (1 + np.exp(-data @ params))
    return np.sum((actual - predicted)**2, axis=0)


def plot(data, params):
    num_plots = data.shape[1] + 1
    scale = 3
    fig, axs = plt.subplots(nrows=num_plots, figsize=(scale, scale * num_plots))

    for i, coefficients in enumerate(params):
        sns.lineplot(y=coefficients, x=range(len(coefficients)), ax=axs[i]).set_title(f"Parameter {i}")

    loss = get_loss(data, params)
    sns.lineplot(x=range(params.shape[1]), y=loss, ax=axs[data.shape[1]]).set_title("SSE")
    plt.show()


def test_sgd_pums(learning_rate=None, min_theta=None, max_theta=None, iters=10, plot_results=False):

    for _ in range(0, iters):
        with sn.Analysis():
            PUMS = sn.Dataset(path=TEST_PUMS_PATH, column_names=TEST_PUMS_NAMES)
            columns = ["married", "sex", "educ"]
            iterations = 100
            sgd_process = sn.dp_sgd(
                data=sn.to_float(PUMS[columns]),
                public_data=sn.to_float(PUMS[columns]),
                # data_2=sn.to_float(PUMS[columns]),
                theta=np.random.uniform(min_theta, max_theta, size=len(columns)),
                learning_rate=learning_rate,
                noise_scale=0.1,
                group_size=10,
                gradient_norm_bound=0.5,
                max_iters=iterations,
                clipping_value=100.,
                sample_size=100,
                param_search_step_size=0.1,
                param_search_max_iters=2
            )

            data = np.array(pd.read_csv(TEST_PUMS_PATH)[columns])

            sgd_process.analysis.release()
            # print([len(x) for x in sgd_process.value])

            if not IS_CI_BUILD and plot_results:
                plot(data, sgd_process.value)
    return sgd_process.value

        # theta_history = pd.DataFrame(
        #     sgd_process.value.reshape((iterations, len(columns))),
        #     columns=["intercept", *columns[1:]])
        #
        # # print(theta_history)
        # melted = pd.melt(theta_history.reset_index(), id_vars='index')
        #
        # sns.lineplot(x='index', y='value', hue='variable',
        #              data=melted)
        # plt.show()


def test_sgd_rust_test_case():
    # Build large test dataset, with n rows, x~uniform; y~binomial(pi); pi = 1/(1+exp(-1 - 1x))
    n = 1000
    m = 2
    data = np.random.uniform(-1, 1, size=(n, m))

    transform = 1.0 / (1.0 + np.exp(1.0 - 3.0 * data[:, 1]))
    data[:, 0] = np.random.binomial(1, transform)

    iterations = 1000

    with sn.Analysis():
        sgd_process = sn.dp_sgd(
            data=sn.to_float(sn.Dataset(value=data)),
            theta=np.array([-0.5, 2.0]),
            learning_rate=0.0000001,
            noise_scale=0.1,
            group_size=0,  # TODO: remove
            gradient_norm_bound=1.0,
            max_iters=iterations,
            clipping_value=100.,
            sample_size=10)

    print("thetas", sgd_process.value)

    if not IS_CI_BUILD:
        plot(data, sgd_process.value)



if __name__ == '__main__':
    results = []
    for learning_rate in np.arange(0.05, 0.5, 0.1):
        for theta in np.arange(0.1, 0.5, 0.1):
            try:
                print("----------------------------")
                print("Learning rate: {}\ttheta: {}".format(learning_rate, theta))
                print("----------------------------")

                values = test_sgd_pums(learning_rate=learning_rate, min_theta=-theta, max_theta=theta, iters=1)

                zipped = list(zip(*values))
                # print("zipped: ", list(zipped))
                filtered = list(filter(lambda x: sum(x) != 0.0, zipped))
                print("filtered: ", filtered)
                print("len: ", len(filtered))
                results.append({'steps': len(filtered), 'learning_rate': learning_rate, 'theta': [-theta, theta]})
            except RuntimeError:
                values = None
                continue
    print(sorted(results, key=lambda x: x['steps']))
